"""An abstract virtual machine for python bytecode.

A VM for python byte code that uses pytype/pytd/cfg to generate a trace of the
program execution.
"""

# We have names like "byte_NOP":
# pylint: disable=invalid-name

# Bytecodes don't always use all their arguments:
# pylint: disable=unused-argument

import collections
import contextlib
import dataclasses
import enum
import functools
import itertools
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from pytype import blocks
from pytype import compare
from pytype import constant_folding
from pytype import datatypes
from pytype import load_pytd
from pytype import metrics
from pytype import preprocess
from pytype import state as frame_state
from pytype import vm_utils
from pytype.abstract import abstract
from pytype.abstract import abstract_utils
from pytype.abstract import function
from pytype.abstract import mixin
from pytype.directors import directors
from pytype.overlays import overlay_dict
from pytype.overlays import overlay as overlay_lib
from pytype.pyc import loadmarshal
from pytype.pyc import opcodes
from pytype.pyc import pyc
from pytype.pyi import parser
from pytype.pytd import slots
from pytype.pytd import visitors
from pytype.typegraph import cfg
from pytype.typegraph import cfg_utils

log = logging.getLogger(__name__)


@dataclasses.dataclass(eq=True, frozen=True)
class LocalOp:
  """An operation local to a VM frame."""

  class Op(enum.Enum):
    ASSIGN = 1
    ANNOTATE = 2

  name: str
  op: "LocalOp.Op"

  def is_assign(self):
    return self.op == self.Op.ASSIGN

  def is_annotate(self):
    return self.op == self.Op.ANNOTATE


class _EnumTracker:
  """Track enum cases for exhaustiveness."""

  def __init__(self, enum_cls):
    self.enum_cls = enum_cls
    self.members = list(enum_cls.get_enum_members(qualified=True))
    self.uncovered = set(self.members)

  def cover(self, enum_case):
    assert enum_case.cls == self.enum_cls
    self.uncovered.discard(enum_case.name)

  def cover_all(self):
    self.uncovered = set()


class _BranchTracker:
  """Track exhaustiveness in pattern matches."""

  def __init__(self, director):
    self.matches = director.matches
    self._tracker = {}
    self._active_ends = set()

  def _add_new_match(self, match_val: abstract.Instance, match_line: int):
    self._tracker[match_line] = _EnumTracker(match_val.cls)
    self._active_ends.add(self.matches.start_to_end[match_line])

  def add_branch(self, op: opcodes.Opcode, match_var: cfg.Variable,
                 case_var: cfg.Variable) -> Optional[bool]:
    """Add a match case branch to the tracker."""
    try:
      match_val = abstract_utils.get_atomic_value(match_var)
      case_val = abstract_utils.get_atomic_value(case_var)
    except abstract_utils.ConversionError:
      return None
    # We currently only implement exhaustiveness matching for enums.
    if not (isinstance(match_val, abstract.Instance) and
            isinstance(match_val.cls, abstract.Class) and
            match_val.cls.is_enum):
      return None
    if not (isinstance(case_val, abstract.Instance) and
            case_val.cls == match_val.cls):
      return None
    match_line = self.matches.match_cases.get(op.line)
    if match_line is None:
      return None
    if match_line not in self._tracker:
      self._add_new_match(match_val, match_line)
    enum_tracker = self._tracker[match_line]
    assert match_val.cls == enum_tracker.enum_cls
    if case_val.name in enum_tracker.uncovered:
      enum_tracker.cover(case_val)
      if enum_tracker.uncovered:
        return None
      else:
        # This is the last remaining case, and will always succeed.
        return True
    else:
      # This has already been covered, and will never succeed.
      return False

  def add_default_branch(self, op: opcodes.Opcode):
    """Add a default match case branch to the tracker."""
    assert op.name == "NOP"
    match_line = self.matches.match_cases.get(op.line)
    if match_line is None:
      return None
    if match_line not in self._tracker:
      return None
    self._tracker[match_line].cover_all()
    return True

  def check_ending(self,
                   line: int,
                   implicit_return: bool = False) -> List[Tuple[int, Set[int]]]:
    """Check if we have ended a match statement with leftover cases."""
    if implicit_return:
      done = set()
      if line in self.matches.match_cases:
        start = self.matches.match_cases[line]
        end = self.matches.start_to_end[start]
        if end in self._active_ends:
          done.add(end)
    else:
      done = {i for i in self._active_ends if line > i}
    ret = []
    for i in done:
      for start in self.matches.end_to_starts[i]:
        uncovered = self._tracker[start].uncovered
        if uncovered:
          ret.append((start, uncovered))
    self._active_ends -= done
    return ret


_opcode_counter = metrics.MapCounter("vm_opcode")


class VirtualMachineError(Exception):
  """For raising errors in the operation of the VM."""


class VirtualMachine:
  """A bytecode VM that generates a cfg as it executes."""

  # This class is defined inside VirtualMachine so abstract.py can use it.
  class VirtualMachineRecursionError(Exception):
    pass

  def __init__(self, ctx):
    """Construct a TypegraphVirtualMachine."""
    self.ctx = ctx  # context.Context
    # The call stack of frames.
    self.frames: List[frame_state.Frame] = []
    # The current frame.
    self.frame: frame_state.Frame = None
    # A map from names to the late annotations that depend on them. Every
    # LateAnnotation depends on a single undefined name, so once that name is
    # defined, we immediately resolve the annotation.
    self.late_annotations: Dict[str, List[abstract.LateAnnotation]] = (
        collections.defaultdict(list))
    # Memoize which overlays are loaded.
    self.loaded_overlays: Dict[str, Optional[overlay_lib.Overlay]] = {}
    self.has_unknown_wildcard_imports: bool = False
    # pyformat: disable
    self.opcode_traces: List[Tuple[
        Optional[opcodes.Opcode],
        Any,
        Tuple[Optional[List[abstract.BaseValue]], ...]
    ]] = []
    # pyformat: enable
    # Track the order of creation of local vars, for attrs and dataclasses.
    self.local_ops: Dict[str, List[LocalOp]] = {}
    # Record the annotated and original values of locals.
    self.annotated_locals: Dict[str, Dict[str, abstract_utils.Local]] = {}
    self.filename: str = None
    self.concrete_classes: List[
        Tuple[abstract.Class, Sequence[frame_state.SimpleFrame]]] = []
    self.functions_type_params_check: List[
        Tuple[abstract.InterpreterFunction, opcodes.Opcode]] = []

    self._maximum_depth = None  # set by run_program() and analyze()
    self._director = None
    self._analyzing = False  # Are we in self.analyze()?
    self._importing = False  # Are we importing another file?
    self._trace_opcodes = True  # whether to trace opcodes
    # If set, we will generate LateAnnotations with this stack rather than
    # logging name errors.
    self._late_annotations_stack = None
    # Mapping of Variables to python variable names. {id: int -> name: str}
    # Note that we don't need to scope this to the frame because we don't reuse
    # variable ids.
    self._var_names = {}
    self._branch_tracker = None

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
      assert val
      data = tuple(get_data(v) for v in val)
    else:
      data = (get_data(val),)
    rec = (op, symbol, data)
    self.opcode_traces.append(rec)

  def remaining_depth(self):
    assert self._maximum_depth is not None
    return self._maximum_depth - len(self.frames)

  def is_at_maximum_depth(self):
    return len(self.frames) > self._maximum_depth

  def run_instruction(
      self, op: opcodes.Opcode, state: frame_state.FrameState
  ) -> frame_state.FrameState:
    """Run a single bytecode instruction.

    Args:
      op: An opcode.
      state: The state just before running this instruction.
    Returns:
      The state right after this instruction that should roll over to the
      subsequent instruction. If this opcode aborts this function (e.g. through
      a 'raise'), then the state's "why" attribute is set to the abort reason.
    Raises:
      VirtualMachineError: if a fatal error occurs.
    """
    _opcode_counter.inc(op.name)
    self.frame.current_opcode = op
    self._importing = "IMPORT" in op.__class__.__name__
    if log.isEnabledFor(logging.INFO):
      vm_utils.log_opcode(op, state, self.frame, len(self.frames))
    # dispatch
    bytecode_fn = getattr(self, f"byte_{op.name}", None)
    if bytecode_fn is None:
      raise VirtualMachineError(f"Unknown opcode: {op.name}")
    state = bytecode_fn(state, op)
    if state.why in ("reraise", "NoReturn"):
      state = state.set_why("exception")
    implicit_return = (
        op.name == "RETURN_VALUE" and
        op.line not in self._director.return_lines)
    chk = self._branch_tracker.check_ending(op.line, implicit_return)
    for line, cases in chk:
      self.ctx.errorlog.incomplete_match(self.frames, line, cases)
    self.frame.current_opcode = None
    return state

  def run_frame(self, frame, node, annotated_locals=None):
    """Run a frame (typically belonging to a method)."""
    self.push_frame(frame)
    frame.states[frame.f_code.first_opcode] = frame_state.FrameState.init(
        node, self.ctx)
    frame_name = frame.f_code.co_name
    if frame_name not in self.local_ops or frame_name != "<module>":
      # abstract_utils.eval_expr creates a temporary frame called "<module>". We
      # don't care to track locals for this frame and don't want it to overwrite
      # the locals of the actual module frame.
      self.local_ops[frame_name] = []
      self.annotated_locals[frame_name] = annotated_locals or {}
    else:
      assert annotated_locals is None
    can_return = False
    return_nodes = []
    finally_tracker = vm_utils.FinallyStateTracker()
    vm_utils.adjust_block_returns(frame.f_code, self._director.block_returns)
    for block in frame.f_code.order:
      state = frame.states.get(block[0])
      if not state:
        log.warning("Skipping block %d, nothing connects to it.", block.id)
        continue
      self.frame.current_block = block
      op = None
      for op in block:
        state = self.run_instruction(op, state)
        # Check if we have to carry forward the return state from an except
        # block to the END_FINALLY opcode.
        new_why = finally_tracker.process(op, state, self.ctx)
        if new_why:
          state = state.set_why(new_why)
        if state.why:
          # we can't process this block any further
          break
      assert op
      if state.why:
        # If we raise an exception or return in an except block do not
        # execute any target blocks it has added.
        if finally_tracker.check_early_exit(state):
          m_frame = self.frame
          assert m_frame is not None
          for target in m_frame.targets[block.id]:
            del frame.states[target]
        # return, raise, or yield. Leave the current frame.
        can_return |= state.why in ("return", "yield")
        return_nodes.append(state.node)
      elif op.carry_on_to_next():
        # We're starting a new block, so start a new CFG node. We don't want
        # nodes to overlap the boundary of blocks.
        state = state.forward_cfg_node()
        frame.states[op.next] = state.merge_into(frame.states.get(op.next))
    vm_utils.update_excluded_types(node, self.ctx)
    self.pop_frame(frame)
    if not return_nodes:
      # Happens if the function never returns. (E.g. an infinite loop)
      assert not frame.return_variable.bindings
      frame.return_variable.AddBinding(self.ctx.convert.unsolvable, [], node)
    else:
      node = self.ctx.join_cfg_nodes(return_nodes)
      if not can_return:
        assert not frame.return_variable.bindings
        # We purposely don't check NoReturn against this function's
        # annotated return type. Raising an error in an unimplemented function
        # and documenting the intended return type in an annotation is a
        # common pattern.
        self._set_frame_return(node, frame,
                               self.ctx.convert.no_return.to_variable(node))
    return node, frame.return_variable

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

  def _call(
      self, state, obj, method_name, args
  ) -> Tuple[frame_state.FrameState, cfg.Variable]:
    state, method = self.load_attr(state, obj, method_name)
    return self.call_function_with_state(state, method, args)

  def make_frame(
      self, node, code, f_globals, f_locals, callargs=None, closure=None,
      new_locals=False, func=None, first_arg=None, substs=()):
    """Create a new frame object, using the given args, globals and locals."""
    if any(code is f.f_code for f in self.frames):
      log.info("Detected recursion in %s", code.co_name or code.co_filename)
      raise self.VirtualMachineRecursionError()

    log.info("make_frame: callargs=%s, f_globals=[%s@%x], f_locals=[%s@%x]",
             vm_utils.repper(callargs),
             type(f_globals).__name__, id(f_globals),
             type(f_locals).__name__, id(f_locals))

    # Implement NEWLOCALS flag. See Objects/frameobject.c in CPython.
    # (Also allow to override this with a parameter, Python 3 doesn't always set
    #  it to the right value, e.g. for class-level code.)
    if code.has_newlocals() or new_locals:
      f_locals = abstract.LazyConcreteDict("locals", {}, self.ctx)

    return frame_state.Frame(node, self.ctx, code, f_globals, f_locals,
                             self.frame, callargs or {}, closure, func,
                             first_arg, substs)

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

  def stack(self, func):
    """Get a frame stack for the given function for error reporting."""
    if isinstance(func, abstract.INTERPRETER_FUNCTION_TYPES) and (
        not self.frame or not self.frame.current_opcode):
      return self.simple_stack(func.get_first_opcode())
    else:
      return self.frames

  def push_abstract_exception(self, state):
    tb = self.ctx.convert.build_list(state.node, [])
    value = self.ctx.convert.create_new_unknown(state.node)
    exctype = self.ctx.convert.create_new_unknown(state.node)
    return state.push(tb, value, exctype)

  def resume_frame(self, node, frame):
    frame.f_back = self.frame
    log.info("resume_frame: %r", frame)
    node, val = self.run_frame(frame, node)
    frame.f_back = None
    return node, val

  def compile_src(self, src, filename=None, mode="exec"):
    """Compile the given source code."""
    code = pyc.compile_src(
        src,
        python_version=self.ctx.python_version,
        python_exe=self.ctx.options.python_exe,
        filename=filename,
        mode=mode)
    return blocks.process_code(code, self.ctx.python_version)

  def run_bytecode(self, node, code, f_globals=None, f_locals=None):
    """Run the given bytecode."""
    if f_globals is not None:
      assert f_locals
    else:
      assert not self.frames
      assert f_locals is None
      # __name__, __doc__, and __package__ are unused placeholder values.
      f_globals = f_locals = abstract.LazyConcreteDict(
          "globals", {
              "__builtins__": self.ctx.loader.builtins,
              "__name__": "__main__",
              "__file__": code.co_filename,
              "__doc__": None,
              "__package__": None,
          }, self.ctx)
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
    self.filename = filename
    self._maximum_depth = maximum_depth
    if self.ctx.python_version >= (3, 8):
      src = preprocess.augment_annotations(src)
    src_tree = directors.parse_src(src, self.ctx.python_version)
    code = self.compile_src(src, filename=filename)
    # In Python 3.8+, opcodes are consistently at the first line of the
    # corresponding source code. Before 3.8, they are on one of the last lines
    # but the exact positioning is unpredictable, so we pass the bytecode to the
    # director to make adjustments based on the opcodes' observed line numbers.
    director = directors.Director(
        src_tree, self.ctx.errorlog, filename, self.ctx.options.disable,
        code if self.ctx.python_version < (3, 8) else None)
    # This modifies the errorlog passed to the constructor.  Kind of ugly,
    # but there isn't a better way to wire both pieces together.
    self.ctx.errorlog.set_error_filter(director.filter_error)
    self._director = director
    self.ctx.options.set_feature_flags(director.features)
    self._branch_tracker = _BranchTracker(director)
    code = blocks.merge_annotations(code, self._director.annotations)
    visitor = vm_utils.FindIgnoredTypeComments(self._director.type_comments)
    pyc.visit(code, visitor)
    for line in visitor.ignored_lines():
      self.ctx.errorlog.ignored_type_comment(self.filename, line,
                                             self._director.type_comments[line])
    code = constant_folding.optimize(code)
    vm_utils.adjust_block_returns(code, self._director.block_returns)

    node = self.ctx.root_node.ConnectNew("init")
    node, f_globals, f_locals, _ = self.run_bytecode(node, code)
    logging.info("Done running bytecode, postprocessing globals")
    # Check for abstract methods on non-abstract classes.
    for val, frames in self.concrete_classes:
      if not val.is_abstract:
        for member in sum((var.data for var in val.members.values()), []):
          if isinstance(member, abstract.Function) and member.is_abstract:
            unwrapped = abstract_utils.maybe_unwrap_decorated_function(member)
            name = unwrapped.data[0].name if unwrapped else member.name
            self.ctx.errorlog.ignored_abstractmethod(frames, val.name, name)
    for annot in itertools.chain.from_iterable(self.late_annotations.values()):
      # If `annot` has already been resolved, this is a no-op. Otherwise, it
      # contains a real name error that will be logged when we resolve it now.
      annot.resolve(node, f_globals, f_locals)
      self.flatten_late_annotation(node, annot, f_globals)
    self.late_annotations = None  # prevent adding unresolvable annotations
    assert not self.frames, "Frames left over!"
    log.info("Final node: <%d>%s", node.id, node.name)
    return node, f_globals.members

  def flatten_late_annotation(self, node, annot, f_globals):
    flattened_expr = annot.flatten_expr()
    if flattened_expr != annot.expr:
      annot.expr = flattened_expr
      f_globals.members[flattened_expr] = annot.to_variable(node)

  def set_var_name(self, var, name):
    self._var_names[var.id] = name

  def get_var_name(self, var):
    """Get the python variable name corresponding to a Variable."""
    # Variables in _var_names correspond to LOAD_* opcodes, which means they
    # have been retrieved from a symbol table like locals() directly by name.
    if var.id in self._var_names:
      return self._var_names[var.id]
    # Look through the source set of a variable's bindings to find the variable
    # created by a LOAD operation. If a variable has multiple sources, don't try
    # to match it to a name.
    sources = set()
    for b in var.bindings:
      for o in b.origins:
        for s in o.source_sets:
          sources |= s
    names = {self._var_names.get(s.variable.id) for s in sources}
    return next(iter(names)) if len(names) == 1 else None

  def binary_operator(self, state, name, report_errors=True):
    state, (x, y) = state.popn(2)
    with self._suppress_opcode_tracing():  # don't trace the magic method call
      state, ret = vm_utils.call_binary_operator(
          state, name, x, y, report_errors=report_errors, ctx=self.ctx)
    self.trace_opcode(None, name, ret)
    return state.push(ret)

  def inplace_operator(self, state, name):
    state, (x, y) = state.popn(2)
    state, ret = vm_utils.call_inplace_operator(state, name, x, y, self.ctx)
    return state.push(ret)

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

  def call_init(self, node, unused_instance):
    # This dummy implementation is overwritten in tracer_vm.py.
    return node

  def init_class(self, node, cls, container=None, extra_key=None):
    # This dummy implementation is overwritten in tracer_vm.py.
    del cls, container, extra_key
    return node, None

  def call_function_with_state(self, state, funcv, posargs, namedargs=None,
                               starargs=None, starstarargs=None,
                               fallback_to_unsolvable=True):
    """Call a function with the given state."""
    assert starargs is None or isinstance(starargs, cfg.Variable)
    assert starstarargs is None or isinstance(starstarargs, cfg.Variable)
    args = function.Args(
        posargs=posargs, namedargs=namedargs, starargs=starargs,
        starstarargs=starstarargs)
    node, ret = function.call_function(
        self.ctx,
        state.node,
        funcv,
        args,
        fallback_to_unsolvable,
        allow_noreturn=True)
    if ret.data == [self.ctx.convert.no_return]:
      state = state.set_why("NoReturn")
    state = state.change_cfg_node(node)
    if len(funcv.data) == 1:
      # Check for test assertions that narrow the type of a variable.
      state = self._check_test_assert(state, funcv, posargs)
    return state, ret

  def call_with_fake_args(self, node0, funcv):
    """Attempt to call the given function with made-up arguments."""
    return node0, self.ctx.new_unsolvable(node0)

  def call_function_from_stack(self, state, num, starargs, starstarargs):
    """Pop arguments for a function and call it."""

    namedargs = {}

    def set_named_arg(node, key, val):
      # If we have no bindings for val, fall back to unsolvable.
      # See test_closures.ClosuresTest.test_undefined_var
      namedargs[key] = val if val.bindings else self.ctx.new_unsolvable(node)

    state, args = state.popn(num)
    if starstarargs:
      kwnames = abstract_utils.get_atomic_python_constant(starstarargs, tuple)
      n = len(args) - len(kwnames)
      for key, arg in zip(kwnames, args[n:]):
        key = self.ctx.convert.value_to_constant(key.data[0], str)
        set_named_arg(state.node, key, arg)
      posargs = args[0:n]
      starstarargs = None
    else:
      posargs = args
    state, func = state.pop()
    state, ret = self.call_function_with_state(
        state, func, posargs, namedargs, starargs, starstarargs)
    return state.push(ret)

  def get_globals_dict(self):
    """Get a real python dict of the globals."""
    return self.frame.f_globals

  def load_from(
      self, state: frame_state.FrameState, store: abstract.LazyConcreteDict,
      name: str, discard_concrete_values: bool = False
  ) -> Tuple[frame_state.FrameState, cfg.Variable]:
    """Load an item out of locals, globals, or builtins."""
    store.load_lazy_attribute(name)
    try:
      member = store.members[name]
    except KeyError:
      return state, self._load_annotation(state.node, name, store)
    bindings = member.Bindings(state.node)
    if (not bindings and self._late_annotations_stack and member.bindings and
        all(isinstance(v, abstract.Module) for v in member.data)):
      # Hack: Evaluation of late annotations may create new nodes not within the
      # normal program flow, causing imports to not be visible, so we pretend
      # that modules are always visible.
      bindings = member.bindings
    if not bindings:
      return state, self._load_annotation(state.node, name, store)
    ret = self.ctx.program.NewVariable()
    self._filter_none_and_paste_bindings(
        state.node, bindings, ret,
        discard_concrete_values=discard_concrete_values)
    self.set_var_name(ret, name)
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
    return self.load_from(state, self.frame.f_locals, name)

  def load_global(self, state, name):
    # The concrete value of typing.TYPE_CHECKING should be preserved; otherwise,
    # concrete values are converted to abstract instances of their types, as we
    # generally can't assume that globals are constant.
    return self.load_from(
        state, self.frame.f_globals, name,
        discard_concrete_values=name != "TYPE_CHECKING")

  def load_special_builtin(self, name):
    if name == "__any_object__":
      # For type_inferencer/tests/test_pgms/*.py, must be a new object
      # each time.
      return abstract.Unknown(self.ctx)
    else:
      return self.ctx.special_builtins.get(name)

  def load_builtin(self, state, name):
    if name == "__undefined__":
      # For values that don't exist. (Unlike None, which is a valid object)
      return state, self.ctx.convert.empty.to_variable(self.ctx.root_node)
    special = self.load_special_builtin(name)
    if special:
      return state, special.to_variable(state.node)
    else:
      return self.load_from(state, self.frame.f_builtins, name)

  def load_constant(self, state, op, raw_const):
    const = self.ctx.convert.constant_to_var(raw_const, node=state.node)
    self.trace_opcode(op, raw_const, const)
    return state.push(const)

  def _load_annotation(self, node, name, store):
    annots = abstract_utils.get_annotations_dict(store.members)
    if annots:
      typ = annots.get_type(node, name)
      if typ:
        _, ret = self.ctx.annotation_utils.init_annotation(node, name, typ)
        store.members[name] = ret
        self.set_var_name(ret, name)
        return ret
    raise KeyError(name)

  def _record_local(self, node, op, name, typ, orig_val=None, final=None):
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
      final: Whether the annotation is tagged Final (None to preserve any
          existing Final tag when updating an existing annotation).
    """
    if orig_val:
      self.current_local_ops.append(LocalOp(name, LocalOp.Op.ASSIGN))
    if typ:
      self.current_local_ops.append(LocalOp(name, LocalOp.Op.ANNOTATE))
    self._update_annotations_dict(
        node, op, name, typ, orig_val, self.current_annotated_locals,
        final=final)

  def _update_annotations_dict(
      self, node, op, name, typ, orig_val, annotations_dict, final=None):
    if name in annotations_dict:
      annotations_dict[name].update(node, op, typ, orig_val)
    else:
      annotations_dict[name] = abstract_utils.Local(node, op, typ, orig_val,
                                                    self.ctx)
    if final is not None:
      annotations_dict[name].final = final

  def _store_value(self, state, name, value, local):
    """Store 'value' under 'name'."""
    m_frame = self.frame
    assert m_frame is not None
    if local:
      target = m_frame.f_locals
    else:
      target = m_frame.f_globals
    node = self.ctx.attribute_handler.set_attribute(state.node, target, name,
                                                    value)
    if target is m_frame.f_globals and self.late_annotations:
      # We sort the annotations so that a parameterized class's base class is
      # resolved before the parameterized class itself.
      for annot in sorted(self.late_annotations[name], key=lambda t: t.expr):
        annot.resolve(node, m_frame.f_globals, m_frame.f_locals)
    return state.change_cfg_node(node)

  def store_local(self, state, name, value):
    """Called when a local is written."""
    return self._store_value(state, name, value, local=True)

  def _process_annotations(self, node, name, value):
    """Process any type annotations in the named value."""
    if not value.data or any(not isinstance(v, mixin.NestedAnnotation)
                             for v in value.data):
      return value
    stack = self.simple_stack()
    typ = self.ctx.annotation_utils.extract_annotation(node, value, name, stack)
    return typ.to_variable(node)

  def _apply_annotation(
      self, state, op, name, orig_val, annotations_dict, check_types):
    """Applies the type annotation, if any, associated with this object."""
    ann = self.ctx.annotation_utils.apply_annotation(
        state.node, op, name, orig_val)
    typ, value = ann.typ, ann.value
    final_violation = False
    local = False
    if annotations_dict is not None:
      # If we are assigning to a member that is in the class annotation dict as
      # Final, don't raise an error if we are simply analysing the same method
      # repeatedly and have hit the STORE_ opcode a second time.
      final_violation = (name in annotations_dict and
                         annotations_dict[name].final and
                         op != annotations_dict[name].last_update_op)
      if annotations_dict is self.current_annotated_locals:
        local = True
        self._record_local(state.node, op, name, typ, orig_val, ann.final)
      elif name not in annotations_dict or not annotations_dict[name].typ:
        # When updating non-local annotations, we only record the first one
        # encountered so that if, say, an instance attribute is annotated in
        # both __init__ and another method, the __init__ annotation is used.
        self._update_annotations_dict(
            state.node, op, name, typ, orig_val, annotations_dict, ann.final)
      if typ is None and name in annotations_dict:
        typ = annotations_dict[name].get_type(state.node, name)
        if typ == self.ctx.convert.unsolvable:
          # An Any annotation can be used to essentially turn off inference in
          # cases where it is causing false positives or other issues.
          value = self.ctx.new_unsolvable(state.node)
    if check_types:
      if final_violation:
        self.ctx.errorlog.assigning_to_final(self.frames, name, local)
      else:
        self.ctx.check_annotation_type_mismatch(
            state.node, name, typ, orig_val, self.frames, allow_none=True)
    return value

  def _pop_and_store(self, state, op, name, local):
    """Pop a value off the stack and store it in a variable."""
    state, orig_val = state.pop()
    annotations_dict = self.current_annotated_locals if local else None
    value = self._apply_annotation(
        state, op, name, orig_val, annotations_dict, check_types=True)
    value = self._process_annotations(state.node, name, value)
    state = state.forward_cfg_node()
    state = self._store_value(state, name, value, local)
    self.trace_opcode(op, name, value)
    return state.forward_cfg_node()

  def _del_name(self, op, state, name, local):
    """Called when a local or global is deleted."""
    value = abstract.Deleted(self.ctx).to_variable(state.node)
    state = state.forward_cfg_node()
    state = self._store_value(state, name, value, local)
    self.trace_opcode(op, name, value)
    return state.forward_cfg_node()

  def _retrieve_attr(
      self, node: cfg.CFGNode, obj: cfg.Variable, attr: str
  ) -> Tuple[cfg.CFGNode, Optional[cfg.Variable], List[cfg.Binding]]:
    """Load an attribute from an object."""
    if (attr == "__class__" and self.ctx.callself_stack and
        obj.data == self.ctx.callself_stack[-1].data):
      return node, self.ctx.new_unsolvable(node), []
    # Resolve the value independently for each value of obj
    result = self.ctx.program.NewVariable()
    log.debug("getting attr %s from %r", attr, obj)
    nodes = []
    values_without_attribute = []
    for val in obj.bindings:
      node2, attr_var = self.ctx.attribute_handler.get_attribute(
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
      return self.ctx.join_cfg_nodes(nodes), result, values_without_attribute
    else:
      return node, None, values_without_attribute

  def _data_is_none(self, x: abstract.BaseValue) -> bool:
    return x.cls == self.ctx.convert.none_type

  def _var_is_none(self, v: cfg.Variable) -> bool:
    return (bool(v.bindings) and
            all(self._data_is_none(b.data) for b in v.bindings))

  def _delete_item(self, state, obj, arg):
    state, _ = self._call(state, obj, "__delitem__", (arg,))
    return state

  def load_attr(self, state, obj, attr):
    """Try loading an attribute, and report errors."""
    node, result, errors = self._retrieve_attr(state.node, obj, attr)
    self._attribute_error_detection(state, attr, errors)
    if result is None:
      result = self.ctx.new_unsolvable(node)
    return state.change_cfg_node(node), result

  def _attribute_error_detection(self, state, attr, errors):
    if not self.ctx.options.report_errors:
      return
    for error in errors:
      combination = [error]
      if self.frame.func:
        combination.append(self.frame.func)
      if state.node.HasCombination(combination):
        self.ctx.errorlog.attribute_error(self.frames, error, attr)

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
              self.ctx.convert.get_maybe_abstract_instance(b.data), [b], node)
        else:
          var.PasteBinding(b, node)
      else:
        var.AddBinding(self.ctx.convert.unsolvable, [b], node)

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
          if self.ctx.program.is_reachable(
              src=self.frame.node, dst=origin.where):
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

  def store_attr(
      self, state: frame_state.FrameState, obj: cfg.Variable, attr: str,
      value: cfg.Variable) -> frame_state.FrameState:
    """Set an attribute on an object."""
    if not obj.bindings:
      log.info("Ignoring setattr on %r", obj)
      return state
    nodes = []
    for val in obj.Filter(state.node, strict=False):
      # TODO(b/172045608): Check whether val.data is a descriptor (i.e. has
      # "__set__")
      nodes.append(
          self.ctx.attribute_handler.set_attribute(state.node, val.data, attr,
                                                   value))
    if nodes:
      return state.change_cfg_node(self.ctx.join_cfg_nodes(nodes))
    else:
      return state

  def del_attr(self, state, obj, attr):
    """Delete an attribute."""
    log.info("Attribute removal does not do anything in the abstract "
             "interpreter")
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
    if self.ctx.options.strict_import:
      # Do not import new modules if we aren't in an IMPORT statement.
      # The exception is if we have an implicit "package" module (e.g.
      # `import a.b.c` adds `a.b` to the list of instantiable modules.)
      if not (self._importing or self.ctx.loader.has_module_prefix(full_name)):
        return None
    try:
      module = self._import_module(name, level)
      # Since we have explicitly imported full_name, add it to the prefix list.
      self.ctx.loader.add_module_prefixes(full_name)
    except (parser.ParseError, load_pytd.BadDependencyError,
            visitors.ContainerError, visitors.SymbolLookupError,
            visitors.LiteralValueError) as e:
      self.ctx.errorlog.pyi_error(self.frames, full_name, e)
      module = self.ctx.convert.unsolvable
    return module

  def _maybe_load_overlay(self, name):
    """Check if a module path is in the overlay dictionary."""
    if name not in overlay_dict.overlays:
      return None
    if name in self.loaded_overlays:
      overlay = self.loaded_overlays[name]
    else:
      overlay = overlay_dict.overlays[name](self.ctx)
      # The overlay should be available only if the underlying pyi is.
      if overlay.ast:
        self.loaded_overlays[name] = overlay
      else:
        overlay = self.loaded_overlays[name] = None
    return overlay

  @functools.lru_cache(maxsize=None)  # pylint: disable=cache-max-size-none
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
        overlay = self._maybe_load_overlay(name)
        if overlay:
          return overlay
        if level == -1 and self.ctx.loader.base_module:
          # Python 2 tries relative imports first.
          ast = (
              self.ctx.loader.import_relative_name(name) or
              self.ctx.loader.import_name(name))
        else:
          ast = self.ctx.loader.import_name(name)
      else:
        # "from .x import *"
        base = self.ctx.loader.import_relative(level)
        if base is None:
          return None
        full_name = base.name + "." + name
        overlay = self._maybe_load_overlay(full_name)
        if overlay:
          return overlay
        ast = self.ctx.loader.import_name(full_name)
    else:
      assert level > 0
      ast = self.ctx.loader.import_relative(level)
    if ast:
      return self.ctx.convert.constant_to_value(
          ast, subst=datatypes.AliasingDict(), node=self.ctx.root_node)
    else:
      return None

  def unary_operator(self, state, name):
    state, x = state.pop()
    state, result = self._call(state, x, name, ())
    state = state.push(result)
    return state

  def _is_classmethod_cls_arg(self, var):
    """True if var is the first arg of a class method in the current frame."""
    if not (self.frame.func and self.frame.first_arg):
      return False

    func = self.frame.func.data
    if func.is_classmethod or func.name.rsplit(".")[-1] == "__new__":
      is_cls = not set(var.data) - set(self.frame.first_arg.data)
      return is_cls
    return False

  def expand_bool_result(self, node, left, right, name, maybe_predicate):
    """Common functionality for 'is' and 'is not'."""
    if (self._is_classmethod_cls_arg(left) or
        self._is_classmethod_cls_arg(right)):
      # If cls is the first argument of a classmethod, it could be bound to
      # either the defining class or one of its subclasses, so `is` is
      # ambiguous.
      return self.ctx.new_unsolvable(node)

    result = self.ctx.program.NewVariable()
    for x in left.bindings:
      for y in right.bindings:
        pyval = maybe_predicate(x.data, y.data)
        result.AddBinding(
            self.ctx.convert.bool_values[pyval], source_set=(x, y), where=node)

    return result

  def _get_aiter(self, state, obj):
    """Get an async iterator from an object."""
    state, func = self.load_attr(state, obj, "__aiter__")
    if func:
      return self.call_function_with_state(state, func, ())
    else:
      return state, self.ctx.new_unsolvable(state.node)

  def _get_iter(self, state, seq, report_errors=True):
    """Get an iterator from a sequence."""
    # TODO(b/201603421): We should iterate through seq's bindings, in order to
    # fetch the attribute on the sequence's class, but two problems prevent us
    # from doing so:
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
        # Call __getitem__(int).
        state, item = self.call_function_with_state(
            state, func, (self.ctx.convert.build_int(state.node),))
        # Create a new iterator from the returned value.
        itr = abstract.Iterator(self.ctx, item).to_variable(state.node)
      else:
        itr = self.ctx.program.NewVariable()
      if report_errors and self.ctx.options.report_errors:
        for m in missing:
          if state.node.HasCombination([m]):
            self.ctx.errorlog.attribute_error(self.frames, m, "__iter__")
    return state, itr

  def byte_NOP(self, state, op):
    # In match statements, `case _` compiles to a NOP
    self._branch_tracker.add_default_branch(op)
    return state

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
      result = self.ctx.convert.build_bool(state.node)
    else:
      # Build a result with True/False values, each bound to appropriate
      # bindings.  Note that bindings that are True get attached to a result
      # that is False and vice versa because this is a NOT operation.
      result = self.ctx.program.NewVariable()
      for b in true_bindings:
        result.AddBinding(
            self.ctx.convert.bool_values[False],
            source_set=(b,),
            where=state.node)
      for b in false_bindings:
        result.AddBinding(
            self.ctx.convert.bool_values[True],
            source_set=(b,),
            where=state.node)
    state = state.push(result)
    return state

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
    try:
      raw_const = self.frame.f_code.co_consts[op.arg]
    except IndexError:
      # We have tried to access an undefined closure variable.
      # There is an associated LOAD_DEREF failure where the error will be
      # raised, so we just return unsolvable here.
      # See test_closures.ClosuresTest.test_undefined_var
      return state.push(self.ctx.new_unsolvable(state.node))
    return self.load_constant(state, op, raw_const)

  def byte_LOAD_FOLDED_CONST(self, state, op):
    const = op.arg
    state, var = constant_folding.build_folded_type(self.ctx, state, const)
    return state.push(var)

  def byte_POP_TOP(self, state, op):
    return state.pop_and_discard()

  def byte_DUP_TOP(self, state, op):
    return state.push(state.top())

  def byte_DUP_TOP_TWO(self, state, op):
    state, (a, b) = state.popn(2)
    return state.push(a, b, a, b)

  def byte_ROT_TWO(self, state, op):
    return state.rotn(2)

  def byte_ROT_THREE(self, state, op):
    return state.rotn(3)

  def byte_ROT_FOUR(self, state, op):
    return state.rotn(4)

  def byte_ROT_N(self, state, op):
    return state.rotn(op.arg)

  def _is_private(self, name):
    return name.startswith("_") and not name.startswith("__")

  def _name_error_or_late_annotation(self, state, name):
    """Returns a late annotation or returns Any and logs a name error."""
    if self._late_annotations_stack and self.late_annotations is not None:
      annot = abstract.LateAnnotation(name, self._late_annotations_stack,
                                      self.ctx)
      log.info("Created %r", annot)
      self.late_annotations[name].append(annot)
      return annot
    else:
      details = vm_utils.get_name_error_details(state, name, self.ctx)
      if details:
        details = "Note: " + details.to_error_message()
      self.ctx.errorlog.name_error(self.frames, name, details=details)
      return self.ctx.convert.unsolvable

  def byte_LOAD_NAME(self, state, op):
    """Load a name. Can be a local, global, or builtin."""
    name = self.frame.f_code.co_names[op.arg]
    try:
      state, val = self.load_local(state, name)
    except KeyError:
      try:
        state, val = self.load_global(state, name)
      except KeyError as e:
        try:
          if self._is_private(name):
            # Private names must be explicitly imported.
            self.trace_opcode(op, name, None)
            raise KeyError(name) from e
          state, val = self.load_builtin(state, name)
        except KeyError:
          if self._is_private(name) or not self.has_unknown_wildcard_imports:
            one_val = self._name_error_or_late_annotation(state, name)
          else:
            one_val = self.ctx.convert.unsolvable
          self.trace_opcode(op, name, None)
          return state.push(one_val.to_variable(state.node))
    vm_utils.check_for_deleted(state, name, val, self.ctx)
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
      # Variables with a ".n" naming scheme are created by the interpreter under
      # the hood to store things like iterators for list comprehensions. Even if
      # something goes wrong, we should not expose this implementation detail to
      # the user.
      if re.fullmatch(r"\.\d+", name):
        val = self.ctx.new_unsolvable(state.node)
      else:
        val = self._name_error_or_late_annotation(state, name).to_variable(
            state.node)
    vm_utils.check_for_deleted(state, name, val, self.ctx)
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
        ret = self._name_error_or_late_annotation(state, name)
        return state.push(ret.to_variable(state.node))
    vm_utils.check_for_deleted(state, name, val, self.ctx)
    self.trace_opcode(op, name, val)
    return state.push(val)

  def byte_STORE_GLOBAL(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    return self._pop_and_store(state, op, name, local=False)

  def byte_DELETE_GLOBAL(self, state, op):
    name = self.frame.f_code.co_names[op.arg]
    return self._del_name(op, state, name, local=False)

  def byte_LOAD_CLOSURE(self, state, op):
    """Retrieves a value out of a cell."""
    return vm_utils.load_closure_cell(state, op, False, self.ctx)

  def byte_LOAD_DEREF(self, state, op):
    """Retrieves a value out of a cell."""
    return vm_utils.load_closure_cell(state, op, True, self.ctx)

  def byte_STORE_DEREF(self, state, op):
    """Stores a value in a closure cell."""
    state, value = state.pop()
    assert isinstance(value, cfg.Variable)
    name = vm_utils.get_closure_var_name(self.frame, op.arg)
    value = self._apply_annotation(
        state, op, name, value, self.current_annotated_locals, check_types=True)
    state = state.forward_cfg_node()
    self.frame.cells[op.arg].PasteVariable(value, state.node)
    state = state.forward_cfg_node()
    self.trace_opcode(op, name, value)
    return state

  def byte_DELETE_DEREF(self, state, op):
    value = abstract.Deleted(self.ctx).to_variable(state.node)
    name = vm_utils.get_closure_var_name(self.frame, op.arg)
    state = state.forward_cfg_node()
    self.frame.cells[op.arg].PasteVariable(value, state.node)
    state = state.forward_cfg_node()
    self.trace_opcode(op, name, value)
    return state

  def byte_LOAD_CLASSDEREF(self, state, op):
    """Retrieves a value out of either locals or a closure cell."""
    name = vm_utils.get_closure_var_name(self.frame, op.arg)
    try:
      state, val = self.load_local(state, name)
      self.trace_opcode(op, name, val)
      return state.push(val)
    except KeyError:
      return vm_utils.load_closure_cell(state, op, False, self.ctx)

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
    ret = self.ctx.program.NewVariable()
    # A variable of the values without a special cmp_rel implementation. Needed
    # because overloaded __eq__ implementations do not necessarily return a
    # bool; see, e.g., test_overloaded in test_cmp.
    leftover_x = self.ctx.program.NewVariable()
    leftover_y = self.ctx.program.NewVariable()
    op_not_eq = op_name not in ("EQ", "NE")
    reported = False
    for b1 in x.bindings:
      for b2 in y.bindings:
        op = getattr(slots, op_name)
        try:
          err = False
          val = compare.cmp_rel(self.ctx, op, b1.data, b2.data)
        except compare.CmpTypeError:
          val = None
          if state.node.HasCombination([b1, b2]):
            err = True
            reported = True  # do not report the wrong-arg-types as well
            self.ctx.errorlog.unsupported_operands(self.frames, op, x, y)
        if val is None:
          # We have to special-case classes here, since getattribute(class, op)
          # gets the class method, not the instance method of the metaclass, and
          # raises an error message referring to the comparator method on
          # `object` in addition to the error thrown by compare.
          # TODO(b/205755440): We fail (with the aforementioned bad error
          # message) when the comparator method is defined on a metaclass, since
          # compare only raises an error for classes with metaclass=type.
          if op_not_eq and isinstance(b1.data, abstract.Class) and err:
            ret.AddBinding(self.ctx.convert.unsolvable, {b1, b2}, state.node)
          elif isinstance(b1.data, abstract.SequenceLength):
            # `None` is a meaningful return value when pattern matching
            ret.AddBinding(self.ctx.convert.bool_values[val], {b1, b2},
                           state.node)
          else:
            leftover_x.AddBinding(b1.data, {b1}, state.node)
            leftover_y.AddBinding(b2.data, {b2}, state.node)
        else:
          ret.AddBinding(self.ctx.convert.bool_values[val], {b1, b2},
                         state.node)
    if leftover_x.bindings:
      op = f"__{op_name.lower()}__"
      # If we do not already have a return value, raise any errors caught by the
      # overloaded comparison method.
      report_errors = op_not_eq and not bool(ret.bindings) and not reported
      state, leftover_ret = vm_utils.call_binary_operator(
          state, op, leftover_x, leftover_y, report_errors=report_errors,
          ctx=self.ctx)
      ret.PasteVariable(leftover_ret, state.node)
    return state, ret

  def _coerce_to_bool(self, node, var, true_val=True):
    """Coerce the values in a variable to bools."""
    bool_var = self.ctx.program.NewVariable()
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
      bool_var.AddBinding(self.ctx.convert.bool_values[const], {b}, node)
    return bool_var

  def _cmp_in(self, state, item, seq, true_val=True):
    """Implementation of CMP_IN/CMP_NOT_IN."""
    state, has_contains = self.load_attr_noerror(state, seq, "__contains__")
    if has_contains:
      state, ret = vm_utils.call_binary_operator(
          state, "__contains__", seq, item, report_errors=True, ctx=self.ctx)
      if ret.bindings:
        ret = self._coerce_to_bool(state.node, ret, true_val=true_val)
    else:
      # For an object without a __contains__ method, cmp_in falls back to
      # checking item against the items produced by seq's iterator.
      state, itr = self._get_iter(state, seq, report_errors=False)
      if len(itr.bindings) < len(seq.bindings):
        # seq does not have any of __contains__, __iter__, and __getitem__.
        # (The last two are checked by _get_iter.)
        self.ctx.errorlog.unsupported_operands(self.frames, "__contains__", seq,
                                               item)
      ret = self.ctx.convert.build_bool(state.node)
    return state, ret

  def _cmp_is_always_supported(self, op_arg):
    """Checks if the comparison should always succeed."""
    return op_arg in slots.CMP_ALWAYS_SUPPORTED

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
    value = self.ctx.program.NewVariable()
    types = []
    stack = list(exc_type.data)
    while stack:
      e = stack.pop()
      if isinstance(e, abstract.Tuple):
        for sub_exc_type in e.pyval:
          sub_value, sub_types = self._instantiate_exception(node, sub_exc_type)
          value.PasteVariable(sub_value)
          types.extend(sub_types)
      elif (isinstance(e, abstract.Instance) and
            e.cls.full_name == "builtins.tuple"):
        sub_exc_type = e.get_instance_type_parameter(abstract_utils.T)
        sub_value, sub_types = self._instantiate_exception(node, sub_exc_type)
        value.PasteVariable(sub_value)
        types.extend(sub_types)
      elif isinstance(e, abstract.Class) and any(
          base.full_name == "builtins.BaseException" or
          isinstance(base, abstract.AMBIGUOUS_OR_EMPTY) for base in e.mro):
        node, instance = self.init_class(node, e)
        value.PasteVariable(instance)
        types.append(e)
      elif isinstance(e, abstract.Union):
        stack.extend(e.options)
      else:
        if not isinstance(e, abstract.AMBIGUOUS_OR_EMPTY):
          if isinstance(e, abstract.Class):
            mro_seqs = [e.mro] if isinstance(e, abstract.Class) else []
            msg = f"{e.name} does not inherit from BaseException"
          else:
            mro_seqs = []
            msg = "Not a class"
          self.ctx.errorlog.mro_error(
              self.frames, e.name, mro_seqs, details=msg)
        value.AddBinding(self.ctx.convert.unsolvable, [], node)
        types.append(None)
    return value, types

  def _replace_abstract_exception(self, state, exc_type):
    """Replace unknowns added by push_abstract_exception with precise values."""
    # When the `try` block is set up, push_abstract_exception pushes on
    # unknowns for the value and exception type. At the beginning of the
    # `except` block, when we know the exception being caught, we can replace
    # the unknowns with more useful variables.
    value, types = self._instantiate_exception(state.node, exc_type)
    if None in types:
      exc_type = self.ctx.new_unsolvable(state.node)
    if self.ctx.python_version >= (3, 8):
      # See SETUP_FINALLY: in 3.8+, we push the exception on twice.
      state, (_, _, tb, _, _) = state.popn(5)
      state = state.push(value, exc_type, tb, value, exc_type)
    else:
      state, _ = state.popn(2)
      state = state.push(value, exc_type)
    return state

  def _compare_op(self, state, op_arg, op):
    """Pops and compares the top two stack values and pushes a boolean."""
    state, (x, y) = state.popn(2)
    match_enum = self._branch_tracker.add_branch(op, x, y)
    if match_enum is not None:
      # The match always succeeds/fails.
      ret = self.ctx.convert.bool_values[match_enum].to_variable(state.node)
      if match_enum is False:  # pylint: disable=g-bool-id-comparison
        case_val = abstract_utils.get_atomic_value(y)
        self.ctx.errorlog.redundant_match(self.frames, case_val.name)
      return state.push(ret)

    # Explicit, redundant, switch statement, to make it easier to address the
    # behavior of individual compare operations:
    if op_arg == slots.CMP_LT:
      state, ret = self._cmp_rel(state, "LT", x, y)
    elif op_arg == slots.CMP_LE:
      state, ret = self._cmp_rel(state, "LE", x, y)
    elif op_arg == slots.CMP_EQ:
      state, ret = self._cmp_rel(state, "EQ", x, y)
    elif op_arg == slots.CMP_NE:
      state, ret = self._cmp_rel(state, "NE", x, y)
    elif op_arg == slots.CMP_GT:
      state, ret = self._cmp_rel(state, "GT", x, y)
    elif op_arg == slots.CMP_GE:
      state, ret = self._cmp_rel(state, "GE", x, y)
    elif op_arg == slots.CMP_IS:
      ret = self.expand_bool_result(state.node, x, y,
                                    "is_cmp", frame_state.is_cmp)
    elif op_arg == slots.CMP_IS_NOT:
      ret = self.expand_bool_result(state.node, x, y,
                                    "is_not_cmp", frame_state.is_not_cmp)
    elif op_arg == slots.CMP_NOT_IN:
      state, ret = self._cmp_in(state, x, y, true_val=False)
    elif op_arg == slots.CMP_IN:
      state, ret = self._cmp_in(state, x, y)
    elif op_arg == slots.CMP_EXC_MATCH:
      state = self._replace_abstract_exception(state, y)
      ret = self.ctx.convert.build_bool(state.node)
    else:
      raise VirtualMachineError("Invalid argument to COMPARE_OP: %d" % op_arg)
    if not ret.bindings and self._cmp_is_always_supported(op_arg):
      # Some comparison operations are always supported, depending on the target
      # Python version. In this case, always return a (boolean) value.
      # (https://docs.python.org/2/library/stdtypes.html#comparisons or
      # (https://docs.python.org/3/library/stdtypes.html#comparisons)
      ret.AddBinding(self.ctx.convert.primitive_class_instances[bool], [],
                     state.node)
    return state.push(ret)

  def byte_COMPARE_OP(self, state, op):
    return self._compare_op(state, op.arg, op)

  def byte_IS_OP(self, state, op):
    if op.arg:
      op_arg = slots.CMP_IS_NOT
    else:
      op_arg = slots.CMP_IS
    return self._compare_op(state, op_arg, op)

  def byte_CONTAINS_OP(self, state, op):
    if op.arg:
      op_arg = slots.CMP_NOT_IN
    else:
      op_arg = slots.CMP_IN
    return self._compare_op(state, op_arg, op)

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

  def _get_type_of_attr_to_store(self, node, op, obj, name):
    """Grabs the __annotations__ dict, if any, with the attribute type."""
    check_type = True
    annotations_dict = None
    for obj_val in obj.data:
      if isinstance(obj_val, abstract.InterpreterClass):
        maybe_cls = obj_val
      else:
        maybe_cls = obj_val.cls
      if isinstance(maybe_cls, abstract.InterpreterClass):
        m_director = self._director
        assert m_director is not None
        if ("__annotations__" not in maybe_cls.members and
            op.line in m_director.annotations):
          # The class has no annotated class attributes but does have an
          # annotated instance attribute.
          cur_annotations_dict = abstract.AnnotationsDict({}, self.ctx)
          maybe_cls.members["__annotations__"] = (
              cur_annotations_dict.to_variable(self.ctx.root_node))
        cur_annotations_dict = abstract_utils.get_annotations_dict(
            maybe_cls.members)
        if cur_annotations_dict:
          cur_annotations_dict = cur_annotations_dict.annotated_locals
      elif (isinstance(maybe_cls, abstract.PyTDClass) and
            maybe_cls != self.ctx.convert.type_type):
        node, attr = self.ctx.attribute_handler.get_attribute(
            node, obj_val, name, obj_val.to_binding(node))
        if attr:
          typ = self.ctx.convert.merge_classes(attr.data)
          cur_annotations_dict = {
              name: abstract_utils.Local(node, op, typ, None, self.ctx)
          }
        else:
          cur_annotations_dict = None
        # In a PyTDClass, we can't distinguish between an inferred type and an
        # annotation. Even though we don't check against the attribute type, we
        # still apply it so that setting an attribute value on an instance of a
        # class doesn't affect the attribute type in other instances.
        check_type = False
        # We can still check for final members being assigned to.
        if name in maybe_cls.final_members:
          self.ctx.errorlog.assigning_to_final(self.frames, name, local=False)
      else:
        cur_annotations_dict = None
      if cur_annotations_dict is not None:
        if annotations_dict is None:
          annotations_dict = cur_annotations_dict
        else:
          for k, v in cur_annotations_dict.items():
            # pylint: disable=unsupported-assignment-operation,unsupported-membership-test
            if k in annotations_dict:
              annotations_dict[k] = abstract_utils.Local.merge(
                  node, op, annotations_dict[k], v)
            else:
              annotations_dict[k] = v
            # pylint: enable=unsupported-assignment-operation,unsupported-membership-test
    return node, annotations_dict, check_type

  def byte_STORE_ATTR(self, state, op):
    """Store an attribute."""
    name = self.frame.f_code.co_names[op.arg]
    state, (val, obj) = state.popn(2)
    node, annotations_dict, check_attribute_types = (
        self._get_type_of_attr_to_store(state.node, op, obj, name))
    state = state.change_cfg_node(node)
    val = self._apply_annotation(
        state, op, name, val, annotations_dict, check_attribute_types)
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
    state, _ = self._call(state, obj, "__setitem__", (key, val))
    return state

  def _record_annotation_dict_store(self, state, obj, subscr, val, op):
    """Record a store_subscr to an __annotations__ dict."""
    try:
      name = abstract_utils.get_atomic_python_constant(subscr, str)
    except abstract_utils.ConversionError:
      pass
    else:
      typ = self.ctx.annotation_utils.extract_annotation(
          state.node,
          val,
          name,
          self.simple_stack(),
          allowed_type_params=self.frame.type_params)
      self._record_annotation(state.node, op, name, typ)

  def byte_STORE_SUBSCR(self, state, op):
    """Implement obj[subscr] = val."""
    state, (val, obj, subscr) = state.popn(3)
    state = state.forward_cfg_node()
    # Check whether obj is the __annotations__ dict.
    if abstract_utils.match_atomic_value(obj, abstract.AnnotationsDict):
      if all(abstract_utils.is_ellipsis(v) for v in val.data):
        # '...' is an experimental "inferred type": see b/213607272.
        pass
      else:
        if abstract_utils.match_atomic_value(val, abstract.FinalAnnotation):
          val = val.data[0].annotation.to_variable(state.node)
        self._record_annotation_dict_store(state, obj, subscr, val, op)
    state = self.store_subscr(state, obj, subscr, val)
    return state

  def byte_DELETE_SUBSCR(self, state, op):
    state, (obj, subscr) = state.popn(2)
    return self.del_subscr(state, obj, subscr)

  def byte_BUILD_TUPLE(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    return state.push(self.ctx.convert.build_tuple(state.node, elts))

  def byte_BUILD_LIST(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    state = state.push(self.ctx.convert.build_list(state.node, elts))
    return state.forward_cfg_node()

  def byte_BUILD_SET(self, state, op):
    count = op.arg
    state, elts = state.popn(count)
    return state.push(self.ctx.convert.build_set(state.node, elts))

  def byte_BUILD_MAP(self, state, op):
    """Build a dictionary."""
    the_map = self.ctx.convert.build_map(state.node)
    state, args = state.popn(2 * op.arg)
    for i in range(op.arg):
      key, val = args[2*i], args[2*i+1]
      state = self.store_subscr(state, the_map, key, val)
    return state.push(the_map)

  def _get_literal_sequence(self, data):
    """Helper function for _unpack_sequence."""
    try:
      return self.ctx.convert.value_to_constant(data, tuple)
    except abstract_utils.ConversionError:
      # Fall back to looking for a literal list and converting to a tuple
      try:
        return tuple(self.ctx.convert.value_to_constant(data, list))
      except abstract_utils.ConversionError:
        for base in data.cls.mro:
          if isinstance(base, abstract.TupleClass) and not base.formal:
            # We've found a TupleClass with concrete parameters, which means
            # we're a subclass of a heterogeneous tuple (usually a
            # typing.NamedTuple instance).
            new_data = self.ctx.convert.merge_values(
                base.instantiate(self.ctx.root_node).data)
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
    rest = self.ctx.convert.build_list(state.node, rest)
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
    nontuple_seq = self.ctx.program.NewVariable()
    has_slurp = n_after > -1
    count = n_before + max(n_after, 0)
    for b in abstract_utils.expand_type_parameter_instances(seq.bindings):
      tup = self._get_literal_sequence(b.data)
      if tup is not None:
        if has_slurp and len(tup) >= count:
          options.append(self._restructure_tuple(state, tup, n_before, n_after))
          continue
        elif len(tup) == count:
          options.append(tup)
          continue
        else:
          self.ctx.errorlog.bad_unpacking(self.frames, len(tup), count)
      nontuple_seq.AddBinding(b.data, {b}, state.node)
    if nontuple_seq.bindings:
      state, itr = self._get_iter(state, nontuple_seq)
      state, result = self._call(state, itr, "__next__", ())
      # For a non-literal iterable, next() should always return the same type T,
      # so we can iterate `count` times in both UNPACK_SEQUENCE and UNPACK_EX,
      # and assign the slurp variable type List[T].
      option = [result for _ in range(count)]
      if has_slurp:
        slurp = self.ctx.convert.build_list_of_type(state.node, result)
        option = option[:n_before] + [slurp] + option[n_before:]
      options.append(option)
    values = tuple(
        self.ctx.convert.build_content(value) for value in zip(*options))
    for value in reversed(values):
      if not value.bindings:
        # For something like
        #   for i, j in enumerate(()):
        #     print j
        # there are no bindings for j, so we have to add an empty binding
        # to avoid a name error on the print statement.
        value = self.ctx.convert.empty.to_variable(state.node)
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
      return state.push(self.ctx.convert.build_slice(state.node, x, y))
    elif op.arg == 3:
      state, (x, y, z) = state.popn(3)
      return state.push(self.ctx.convert.build_slice(state.node, x, y, z))
    else:       # pragma: no cover
      raise VirtualMachineError(f"Strange BUILD_SLICE count: {op.arg!r}")

  def byte_LIST_APPEND(self, state, op):
    # Used by the compiler e.g. for [x for x in ...]
    count = op.arg
    state, val = state.pop()
    the_list = state.peek(count)
    state, _ = self._call(state, the_list, "append", (val,))
    return state

  def byte_LIST_EXTEND(self, state, op):
    """Pops top-of-stack and uses it to extend the list at stack[op.arg]."""
    state, update = state.pop()
    target = state.peek(op.arg)
    if not all(abstract_utils.is_concrete_list(v) for v in target.data):
      state, _ = self._call(state, target, "extend", (update,))
      return state

    # Is the list we're constructing going to be the argument list for a
    # function call? If so, we will keep any abstract.Splat objects around so we
    # can unpack the function arguments precisely. Otherwise, splats will be
    # converted to indefinite iterables.
    keep_splats = False
    next_op = op
    # Before Python 3.9, BUILD_TUPLE_UNPACK took care of tuple unpacking. In
    # 3.9+, this opcode is replaced by LIST_EXTEND+LIST_TO_TUPLE+CALL_FUNCTION,
    # so CALL_FUNCTION needs to be considered as consuming the list.
    if self.ctx.python_version >= (3, 9):
      stop_classes = blocks.STORE_OPCODES + (opcodes.CALL_FUNCTION,)
    else:
      stop_classes = blocks.STORE_OPCODES
    while next_op:
      next_op = next_op.next
      if isinstance(next_op, opcodes.CALL_FUNCTION_EX):
        keep_splats = True
        break
      elif next_op.__class__ in stop_classes:
        break

    update_elements = vm_utils.unpack_iterable(state.node, update, self.ctx)
    if not keep_splats and any(
        abstract_utils.is_var_splat(x) for x in update_elements):
      for target_value in target.data:
        vm_utils.merge_indefinite_iterables(
            state.node, target_value, update_elements)
    else:
      for target_value in target.data:
        target_value.pyval.extend(update_elements)
        for update_value in update.data:
          update_param = update_value.get_instance_type_parameter(
              abstract_utils.T, state.node)
          # We use Instance.merge_instance_type_parameter because the List
          # implementation also sets could_contain_anything to True.
          abstract.Instance.merge_instance_type_parameter(
              target_value, state.node, abstract_utils.T, update_param)
    return state

  def byte_SET_ADD(self, state, op):
    # Used by the compiler e.g. for {x for x in ...}
    count = op.arg
    state, val = state.pop()
    the_set = state.peek(count)
    state, _ = self._call(state, the_set, "add", (val,))
    return state

  def byte_SET_UPDATE(self, state, op):
    state, update = state.pop()
    target = state.peek(op.arg)
    state, _ = self._call(state, target, "update", (update,))
    return state

  def byte_MAP_ADD(self, state, op):
    """Implements the MAP_ADD opcode."""
    # Used by the compiler e.g. for {x, y for x, y in ...}
    count = op.arg
    # In 3.8+, the value is at the top of the stack, followed by the key. Before
    # that, it's the other way around.
    state, item = state.popn(2)
    if self.ctx.python_version >= (3, 8):
      key, val = item
    else:
      val, key = item
    the_map = state.peek(count)
    state, _ = self._call(state, the_map, "__setitem__", (key, val))
    return state

  def byte_DICT_MERGE(self, state, op):
    # DICT_MERGE is like DICT_UPDATE but raises an exception for duplicate keys.
    return self.byte_DICT_UPDATE(state, op)

  def byte_DICT_UPDATE(self, state, op):
    """Pops top-of-stack and uses it to update the dict at stack[op.arg]."""
    state, update = state.pop()
    target = state.peek(op.arg)

    def pytd_update(state):
      state, _ = self._call(state, target, "update", (update,))
      return state

    if not all(abstract_utils.is_concrete_dict(v) for v in target.data):
      return pytd_update(state)
    try:
      update_value = abstract_utils.get_atomic_python_constant(update, dict)
    except abstract_utils.ConversionError:
      return pytd_update(state)
    for abstract_target_value in target.data:
      for k, v in update_value.items():
        abstract_target_value.set_str_item(state.node, k, v)
    return state

  def byte_PRINT_EXPR(self, state, op):
    # Only used in the interactive interpreter, not in modules.
    return state.pop_and_discard()

  def byte_JUMP_IF_TRUE_OR_POP(self, state, op):
    return vm_utils.jump_if(state, op, self.ctx, jump_if_val=True, or_pop=True)

  def byte_JUMP_IF_FALSE_OR_POP(self, state, op):
    return vm_utils.jump_if(state, op, self.ctx, jump_if_val=False, or_pop=True)

  def byte_JUMP_IF_TRUE(self, state, op):
    return vm_utils.jump_if(state, op, self.ctx, jump_if_val=True)

  def byte_JUMP_IF_FALSE(self, state, op):
    return vm_utils.jump_if(state, op, self.ctx, jump_if_val=False)

  def byte_POP_JUMP_IF_TRUE(self, state, op):
    return vm_utils.jump_if(state, op, self.ctx, pop=True, jump_if_val=True)

  def byte_POP_JUMP_IF_FALSE(self, state, op):
    return vm_utils.jump_if(state, op, self.ctx, pop=True, jump_if_val=False)

  def byte_JUMP_FORWARD(self, state, op):
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_JUMP_ABSOLUTE(self, state, op):
    self.store_jump(op.target, state.forward_cfg_node())
    return state

  def byte_JUMP_IF_NOT_EXC_MATCH(self, state, op):
    state, (unused_exc, exc_type) = state.popn(2)
    # At runtime, this opcode calls isinstance(exc, exc_type) and pushes the
    # result onto the stack. Instead, we use exc_type to refine the type of the
    # exception instance still on the stack and push on an indefinite result for
    # the isinstance call.
    state = self._replace_abstract_exception(state, exc_type)
    state = state.push(self.ctx.convert.bool_values[None].to_variable(
        state.node))
    return vm_utils.jump_if(state, op, self.ctx, pop=True, jump_if_val=False)

  def byte_SETUP_LOOP(self, state, op):
    # We ignore the implicit jump in SETUP_LOOP; the interpreter never takes it.
    return vm_utils.push_block(state, "loop")

  def byte_GET_ITER(self, state, op):
    """Get the iterator for an object."""
    state, seq = state.pop()
    state, itr = self._get_iter(state, seq)
    # Push the iterator onto the stack and return.
    return state.push(itr)

  def store_jump(self, target, state):
    assert target
    assert self.frame is not None
    self.frame.targets[self.frame.current_block.id].append(target)
    self.frame.states[target] = state.merge_into(self.frame.states.get(target))

  def byte_FOR_ITER(self, state, op):
    self.store_jump(op.target, state.pop_and_discard())
    state, f = self.load_attr(state, state.top(), "__next__")
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

  def _setup_except(self, state, op):
    """Sets up an except block."""
    # Assume that it's possible to throw the exception at the first
    # instruction of the code:
    jump_state = self.push_abstract_exception(state)
    if self.ctx.python_version >= (3, 8):
      # I have no idea why we need to push the exception twice! See
      # test_exceptions.TestExceptions.test_reuse_name for a test that fails if
      # we don't do this.
      jump_state = self.push_abstract_exception(jump_state)
    self.store_jump(op.target, jump_state)
    return vm_utils.push_block(state, "setup-except")

  # Note: this opcode is removed in Python 3.8.
  def byte_SETUP_EXCEPT(self, state, op):
    return self._setup_except(state, op)

  def is_setup_except(self, op):
    """Check whether op is equivalent to a SETUP_EXCEPT opcode."""
    # In Python 3.8+, exception setup is done using the SETUP_FINALLY opcode.
    # Before that, there was a separate SETUP_EXCEPT opcode.
    if self.ctx.python_version >= (3, 8):
      if isinstance(op, opcodes.SETUP_FINALLY):
        for i, block in enumerate(self.frame.f_code.order):
          if block.id == op.arg:
            if not any(isinstance(o, opcodes.BEGIN_FINALLY)
                       for o in self.frame.f_code.order[i-1]):
              return True
            break
      return False
    else:
      return isinstance(op, opcodes.SETUP_EXCEPT)

  def byte_SETUP_FINALLY(self, state, op):
    """Implements the SETUP_FINALLY opcode."""
    # In Python 3.8+, SETUP_FINALLY handles setup for both except and finally
    # blocks. Examine the targeted block to determine which setup to do.
    if self.is_setup_except(op):
      return self._setup_except(state, op)
    # Emulate finally by connecting the try to the finally block (with
    # empty reason/why/continuation):
    self.store_jump(op.target,
                    state.push(self.ctx.convert.build_none(state.node)))
    return vm_utils.push_block(state, "finally")

  # New python3.8+ exception handling opcodes:
  # BEGIN_FINALLY, END_ASYNC_FOR, CALL_FINALLY, POP_FINALLY

  def byte_BEGIN_FINALLY(self, state, op):
    return state.push(self.ctx.convert.build_none(state.node))

  def byte_CALL_FINALLY(self, state, op):
    return state

  def byte_END_ASYNC_FOR(self, state, op):
    state, _ = state.popn(7)
    return state

  def byte_POP_FINALLY(self, state, op):
    """Implements POP_FINALLY."""
    preserve_tos = op.arg
    if preserve_tos:
      state, saved_tos = state.pop()
    state, tos = state.pop()
    if any(d != self.ctx.convert.none and d.cls != self.ctx.convert.int_type
           for d in tos.data):
      state, _ = state.popn(5)
    if preserve_tos:
      state = state.push(saved_tos)
    return state

  def byte_POP_BLOCK(self, state, op):
    state, _ = state.pop_block()
    return state

  def byte_RAISE_VARARGS(self, state, op):
    """Raise an exception."""
    argc = op.arg
    state, _ = state.popn(argc)
    if argc == 0 and state.exception:
      return state.set_why("reraise")
    else:
      state = state.set_exception()
      return state.set_why("exception")

  def byte_POP_EXCEPT(self, state, op):  # Python 3 only
    # We don't push the special except-handler block, so we don't need to
    # pop it, either.
    if self.ctx.python_version >= (3, 8):
      state, _ = state.popn(3)
    return state

  def byte_SETUP_WITH(self, state, op):
    """Starts a 'with' statement. Will push a block."""
    state, ctxmgr = state.pop()
    level = len(state.data_stack)
    state, exit_method = self.load_attr(state, ctxmgr, "__exit__")
    state = state.push(exit_method)
    state, ctxmgr_obj = self._call(state, ctxmgr, "__enter__", ())
    state = vm_utils.push_block(state, "finally", level)
    return state.push(ctxmgr_obj)

  def _with_cleanup_start(self, state, op):
    """Implements WITH_CLEANUP_START before Python 3.8."""
    state, u = state.pop()  # pop 'None'
    state, exit_func = state.pop()
    state = state.push(u)
    state = state.push(self.ctx.convert.build_none(state.node))
    v = self.ctx.convert.build_none(state.node)
    w = self.ctx.convert.build_none(state.node)
    state, suppress_exception = self.call_function_with_state(
        state, exit_func, (u, v, w))
    return state.push(suppress_exception)

  def _with_cleanup_start_3_8(self, state, op):
    """Implements WITH_CLEANUP_START in Python 3.8+."""
    tos = state.top()
    if tos.data == [self.ctx.convert.none]:
      return self._with_cleanup_start(state, op)
    state, (w, v, u, *rest, exit_func) = state.popn(7)
    state = state.push(*rest)
    state = state.push(self.ctx.convert.build_none(state.node))
    state = state.push(w, v, u)
    state, suppress_exception = self.call_function_with_state(
        state, exit_func, (u, v, w))
    return state.push(suppress_exception)

  def byte_WITH_CLEANUP_START(self, state, op):
    """Called to start cleaning up a with block. Calls the exit handlers etc."""
    if self.ctx.python_version >= (3, 8):
      return self._with_cleanup_start_3_8(state, op)
    else:
      return self._with_cleanup_start(state, op)

  def byte_WITH_CLEANUP_FINISH(self, state, op):
    """Called to finish cleaning up a with block."""
    state, suppress_exception = state.pop()
    state, second = state.pop()
    if (suppress_exception.data == [self.ctx.convert.true] and
        second.data != [self.ctx.convert.none]):
      state = state.push(self.ctx.convert.build_none(state.node))
    return state

  def _convert_kw_defaults(self, values):
    kw_defaults = {}
    for i in range(0, len(values), 2):
      key_var, value = values[i:i + 2]
      key = abstract_utils.get_atomic_python_constant(key_var)
      kw_defaults[key] = value
    return kw_defaults

  def _get_extra_closure_args(self, state, arg):
    """Get closure annotations and defaults from the stack."""
    num_pos_defaults = arg & 0xff
    num_kw_defaults = (arg >> 8) & 0xff
    state, raw_annotations = state.popn((arg >> 16) & 0x7fff)
    state, kw_defaults = state.popn(2 * num_kw_defaults)
    state, pos_defaults = state.popn(num_pos_defaults)
    free_vars = None  # Python < 3.6 does not handle closure vars here.
    kw_defaults = self._convert_kw_defaults(kw_defaults)
    annot = self.ctx.annotation_utils.convert_function_annotations(
        state.node, raw_annotations)
    return state, pos_defaults, kw_defaults, annot, free_vars

  def _get_extra_function_args(self, state, arg):
    """Get function annotations and defaults from the stack."""
    free_vars = None
    pos_defaults = ()
    kw_defaults = {}
    annot = {}
    if arg & loadmarshal.MAKE_FUNCTION_HAS_FREE_VARS:
      state, free_vars = state.pop()
    if arg & loadmarshal.MAKE_FUNCTION_HAS_ANNOTATIONS:
      state, packed_annot = state.pop()
      # In Python 3.10+, packed_annot is a tuple of variables:
      # (param_name1, param_type1, param_name2, param_type2, ...)
      # Previously, it was a name->param_type dictionary.
      if self.ctx.python_version >= (3, 10):
        annot_seq = abstract_utils.get_atomic_python_constant(
            packed_annot, tuple)
        double_num_annots = len(annot_seq)
        assert not double_num_annots % 2
        annot = {}
        for i in range(double_num_annots // 2):
          name = abstract_utils.get_atomic_python_constant(annot_seq[i*2], str)
          annot[name] = annot_seq[i*2 + 1]
      else:
        annot = abstract_utils.get_atomic_python_constant(packed_annot, dict)
      for k in annot:
        annot[k] = self.ctx.annotation_utils.convert_function_type_annotation(
            k, annot[k])
    if arg & loadmarshal.MAKE_FUNCTION_HAS_KW_DEFAULTS:
      state, packed_kw_def = state.pop()
      kw_defaults = abstract_utils.get_atomic_python_constant(
          packed_kw_def, dict)
    if arg & loadmarshal.MAKE_FUNCTION_HAS_POS_DEFAULTS:
      state, packed_pos_def = state.pop()
      pos_defaults = abstract_utils.get_atomic_python_constant(
          packed_pos_def, tuple)
    annot = self.ctx.annotation_utils.convert_annotations_list(
        state.node, annot.items())
    return state, pos_defaults, kw_defaults, annot, free_vars

  def byte_MAKE_FUNCTION(self, state, op):
    """Create a function and push it onto the stack."""
    state, name_var = state.pop()
    name = abstract_utils.get_atomic_python_constant(name_var)
    state, code = state.pop()
    state, defaults, kw_defaults, annot, free_vars = (
        self._get_extra_function_args(state, op.arg))
    globs = self.get_globals_dict()
    fn = vm_utils.make_function(
        name, state.node, code, globs, defaults, kw_defaults, annotations=annot,
        closure=free_vars, opcode=op, ctx=self.ctx)
    assert self._director is not None
    if op.line in self._director.decorators:
      fn.data[0].is_decorated = True
    vm_utils.process_function_type_comment(state.node, op, fn.data[0], self.ctx)
    self.trace_opcode(op, name, fn)
    self.trace_functiondef(fn)
    return state.push(fn)

  def byte_MAKE_CLOSURE(self, state, op):
    """Make a function that binds local variables."""
    state, name_var = state.pop()
    name = abstract_utils.get_atomic_python_constant(name_var)
    state, (closure, code) = state.popn(2)
    state, defaults, kw_defaults, annot, _ = (
        self._get_extra_closure_args(state, op.arg))
    globs = self.get_globals_dict()
    fn = vm_utils.make_function(
        name, state.node, code, globs, defaults, kw_defaults, annotations=annot,
        closure=closure, opcode=op, ctx=self.ctx)
    self.trace_functiondef(fn)
    return state.push(fn)

  def byte_CALL_FUNCTION(self, state, op):
    return self.call_function_from_stack(state, op.arg, None, None)

  def byte_CALL_FUNCTION_VAR(self, state, op):
    state, starargs = self.pop_varargs(state)
    starargs = vm_utils.ensure_unpacked_starargs(state.node, starargs, self.ctx)
    return self.call_function_from_stack(state, op.arg, starargs, None)

  def byte_CALL_FUNCTION_KW(self, state, op):
    state, kwargs = self.pop_kwargs(state)
    return self.call_function_from_stack(state, op.arg, None, kwargs)

  def byte_CALL_FUNCTION_VAR_KW(self, state, op):
    state, kwargs = self.pop_kwargs(state)
    state, starargs = self.pop_varargs(state)
    starargs = vm_utils.ensure_unpacked_starargs(state.node, starargs, self.ctx)
    return self.call_function_from_stack(state, op.arg, starargs, kwargs)

  def byte_CALL_FUNCTION_EX(self, state, op):
    """Call a function."""
    if op.arg & loadmarshal.CALL_FUNCTION_EX_HAS_KWARGS:
      state, starstarargs = state.pop()
    else:
      starstarargs = None
    state, starargs = state.pop()
    starargs = vm_utils.ensure_unpacked_starargs(state.node, starargs, self.ctx)
    state, fn = state.pop()
    state, ret = self.call_function_with_state(
        state, fn, (), namedargs=None, starargs=starargs,
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
    return state.push(self.ctx.new_unsolvable(state.node))

  def byte_IMPORT_NAME(self, state, op):
    """Import a single module."""
    full_name = self.frame.f_code.co_names[op.arg]
    # The identifiers in the (unused) fromlist are repeated in IMPORT_FROM.
    state, (level_var, fromlist) = state.popn(2)
    assert self._director is not None
    if op.line in self._director.ignore:
      # "import name  # type: ignore"
      self.trace_opcode(op, full_name, None)
      return state.push(self.ctx.new_unsolvable(state.node))
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
      self.ctx.errorlog.import_error(self.frames, name)
      module = self.ctx.convert.unsolvable
    mod = module.to_variable(state.node)
    self.trace_opcode(op, full_name, mod)
    return state.push(mod)

  def byte_IMPORT_FROM(self, state, op):
    """IMPORT_FROM is mostly like LOAD_ATTR but doesn't pop the container."""
    name = self.frame.f_code.co_names[op.arg]
    if op.line in self._director.ignore:
      # "from x import y  # type: ignore"
      # TODO(mdemello): Should we add some sort of signal data to indicate that
      # this should be treated as resolvable even though there is no module?
      self.trace_opcode(op, name, None)
      return state.push(self.ctx.new_unsolvable(state.node))
    module = state.top()
    state, attr = self.load_attr_noerror(state, module, name)
    if attr is None:
      full_name = module.data[0].name + "." + name
      self.ctx.errorlog.import_error(self.frames, full_name)
      attr = self.ctx.new_unsolvable(state.node)
    self.trace_opcode(op, name, attr)
    return state.push(attr)

  def byte_LOAD_BUILD_CLASS(self, state, op):
    cls = abstract.BuildClass(self.ctx).to_variable(state.node)
    assert self._director is not None
    if op.line in self._director.decorators:
      # Will be copied into the abstract.InterpreterClass
      cls.data[0].is_decorated = True
    self.trace_opcode(op, "", cls)
    return state.push(cls)

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
    return False  # overwritten in tracer_vm.py

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
    if (self.ctx.options.no_return_any and
        any(d == self.ctx.convert.unsolvable for d in var.data)):
      self.ctx.errorlog.any_return_type(self.frames)
    self._set_frame_return(state.node, self.frame, var)
    return state.set_why("return")

  def byte_IMPORT_STAR(self, state, op):
    """Pops a module and stores all its contents in locals()."""
    # TODO(b/159041010): this doesn't use __all__ properly.
    state, mod_var = state.pop()
    mod = abstract_utils.get_atomic_value(mod_var)
    if isinstance(mod, (abstract.Unknown, abstract.Unsolvable)):
      self.has_unknown_wildcard_imports = True
      return state
    log.info("%r", mod)
    for name, var in mod.items():
      if name[0] != "_" or name == "__getattr__":
        state = self.store_local(state, name, var)
    return state

  def byte_SETUP_ANNOTATIONS(self, state, op):
    """Sets up variable annotations in locals()."""
    annotations = abstract.AnnotationsDict(self.current_annotated_locals,
                                           self.ctx).to_variable(state.node)
    return self.store_local(state, "__annotations__", annotations)

  def _record_annotation(self, node, op, name, typ):
    # Annotations in self._director are handled by _apply_annotation.
    assert self.frame is not None and self._director is not None
    if self.frame.current_opcode.line not in self._director.annotations:
      self._record_local(node, op, name, typ)

  def byte_STORE_ANNOTATION(self, state, op):
    """Implementation of the STORE_ANNOTATION opcode."""
    state, annotations_var = self.load_local(state, "__annotations__")
    name = self.frame.f_code.co_names[op.arg]
    state, value = state.pop()
    typ = self.ctx.annotation_utils.extract_annotation(
        state.node,
        value,
        name,
        self.simple_stack(),
        allowed_type_params=self.frame.type_params)
    self._record_annotation(state.node, op, name, typ)
    key = self.ctx.convert.primitive_class_instances[str]
    state = self.store_subscr(
        state, annotations_var, key.to_variable(state.node), value)
    return self.store_local(state, "__annotations__", annotations_var)

  def byte_GET_YIELD_FROM_ITER(self, state, op):
    """Implementation of the GET_YIELD_FROM_ITER opcode."""
    # Do nothing with TOS bindings that are generator iterators or coroutines;
    # call GET_ITER on the rest.
    get_iter = self.ctx.program.NewVariable()
    unchanged = self.ctx.program.NewVariable()
    state, tos = state.pop()
    for b in tos.bindings:
      if b.data.full_name in ("builtins.generator", "builtins.coroutine"):
        unchanged.PasteBinding(b)
      else:
        get_iter.PasteBinding(b)
    if get_iter.bindings:
      state = state.push(get_iter)
      state = self.byte_GET_ITER(state, op)
      state.peek(0).PasteVariable(unchanged)
    else:
      state = state.push(unchanged)
    return state

  def byte_BUILD_LIST_UNPACK(self, state, op):
    return vm_utils.unpack_and_build(state, op.arg, self.ctx.convert.build_list,
                                     self.ctx.convert.list_type, self.ctx)

  def byte_LIST_TO_TUPLE(self, state, op):
    """Convert the list at the top of the stack to a tuple."""
    del op  # unused
    state, lst_var = state.pop()
    tup_var = self.ctx.program.NewVariable()
    for b in lst_var.bindings:
      if abstract_utils.is_concrete_list(b.data):
        tup_var.AddBinding(
            self.ctx.convert.tuple_to_value(b.data.pyval), {b}, state.node)
      else:
        param = b.data.get_instance_type_parameter(abstract_utils.T)
        tup = abstract.Instance(self.ctx.convert.tuple_type, self.ctx)
        tup.merge_instance_type_parameter(state.node, abstract_utils.T, param)
        tup_var.AddBinding(tup, {b}, state.node)
    return state.push(tup_var)

  def byte_BUILD_MAP_UNPACK(self, state, op):
    state, maps = state.popn(op.arg)
    args = vm_utils.build_map_unpack(state, maps, self.ctx)
    return state.push(args)

  def byte_BUILD_MAP_UNPACK_WITH_CALL(self, state, op):
    state, maps = state.popn(op.arg)
    args = vm_utils.build_map_unpack(state, maps, self.ctx)
    return state.push(args)

  def byte_BUILD_TUPLE_UNPACK(self, state, op):
    return vm_utils.unpack_and_build(
        state, op.arg, self.ctx.convert.build_tuple,
        self.ctx.convert.tuple_type, self.ctx)

  def byte_BUILD_TUPLE_UNPACK_WITH_CALL(self, state, op):
    state, seq = vm_utils.pop_and_unpack_list(state, op.arg, self.ctx)
    ret = vm_utils.build_function_args_tuple(state.node, seq, self.ctx)
    return state.push(ret)

  def byte_BUILD_SET_UNPACK(self, state, op):
    return vm_utils.unpack_and_build(state, op.arg, self.ctx.convert.build_set,
                                     self.ctx.convert.set_type, self.ctx)

  def byte_SETUP_ASYNC_WITH(self, state, op):
    state, res = state.pop()
    level = len(state.data_stack)
    state = vm_utils.push_block(state, "finally", level)
    return state.push(res)

  def byte_FORMAT_VALUE(self, state, op):
    if op.arg & loadmarshal.FVS_MASK:
      state = state.pop_and_discard()
    # FORMAT_VALUE pops, formats and pushes back a string, so we just need to
    # push a new string onto the stack.
    state = state.pop_and_discard()
    ret = abstract.Instance(self.ctx.convert.str_type, self.ctx)
    return state.push(ret.to_variable(state.node))

  def byte_BUILD_CONST_KEY_MAP(self, state, op):
    state, keys = state.pop()
    keys = abstract_utils.get_atomic_python_constant(keys, tuple)
    the_map = self.ctx.convert.build_map(state.node)
    assert len(keys) == op.arg
    for key in reversed(keys):
      state, val = state.pop()
      state = self.store_subscr(state, the_map, key, val)
    return state.push(the_map)

  def byte_BUILD_STRING(self, state, op):
    # TODO(mdemello): Test this.
    state, _ = state.popn(op.arg)
    ret = abstract.Instance(self.ctx.convert.str_type, self.ctx)
    return state.push(ret.to_variable(state.node))

  def byte_GET_AITER(self, state, op):
    """Implementation of the GET_AITER opcode."""
    state, obj = state.pop()
    state, itr = self._get_aiter(state, obj)
    # Push the iterator onto the stack and return.
    state = state.push(itr)
    return state

  def byte_GET_ANEXT(self, state, op):
    """Implementation of the GET_ANEXT opcode."""
    state, ret = self._call(state, state.top(), "__anext__", ())
    if not self._check_return(state.node, ret, self.ctx.convert.awaitable_type):
      ret = self.ctx.new_unsolvable(state.node)
    return state.push(ret)

  def byte_BEFORE_ASYNC_WITH(self, state, op):
    """Implementation of the BEFORE_ASYNC_WITH opcode."""
    # Pop a context manager and push its `__aexit__` and `__aenter__()`.
    state, ctxmgr = state.pop()
    state, aexit_method = self.load_attr(state, ctxmgr, "__aexit__")
    state = state.push(aexit_method)
    state, ctxmgr_obj = self._call(state, ctxmgr, "__aenter__", ())
    return state.push(ctxmgr_obj)

  def byte_GET_AWAITABLE(self, state, op):
    """Implementation of the GET_AWAITABLE opcode."""
    state, obj = state.pop()
    state, ret = vm_utils.to_coroutine(state, obj, True, self.ctx)
    if not self._check_return(state.node, ret, self.ctx.convert.awaitable_type):
      ret = self.ctx.new_unsolvable(state.node)
    return state.push(ret)

  def byte_YIELD_FROM(self, state, op):
    """Implementation of the YIELD_FROM opcode."""
    state, unused_none_var = state.pop()
    state, var = state.pop()
    result = self.ctx.program.NewVariable()
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
                                      "builtins.coroutine",
                                      "builtins.generator")):
        if val.cls.full_name == "typing.Awaitable":
          ret_var = val.get_instance_type_parameter(abstract_utils.T)
        else:
          ret_var = val.get_instance_type_parameter(abstract_utils.V)
        if ret_var.bindings:
          result.PasteVariable(ret_var, state.node, {b})
        else:
          result.AddBinding(self.ctx.convert.unsolvable, {b}, state.node)
      else:
        result.AddBinding(val, {b}, state.node)
    if not result.bindings:
      result.AddBinding(self.ctx.convert.unsolvable, [], state.node)
    return state.push(result)

  def byte_LOAD_METHOD(self, state, op):
    """Implementation of the LOAD_METHOD opcode."""
    name = self.frame.f_code.co_names[op.arg]
    state, self_obj = state.pop()
    state, result = self.load_attr(state, self_obj, name)
    # https://docs.python.org/3/library/dis.html#opcode-LOAD_METHOD says that
    # this opcode should push two values onto the stack: either the unbound
    # method and its `self` or NULL and the bound method. However, pushing only
    # the bound method and modifying CALL_METHOD accordingly works in all cases
    # we've tested.
    self.trace_opcode(op, name, (self_obj, result))
    return state.push(result)

  def _store_new_var_in_local(self, state, var, new_var):
    """Assign a new var to a variable in locals."""
    varname = self.get_var_name(var)
    if not varname or varname not in self.frame.f_locals.pyval:
      # We cannot store the new value back in locals.
      return state
    # TODO(mdemello): Do we need to create two new nodes for this? Code copied
    # from _pop_and_store, but there might be a reason to create two nodes there
    # that does not apply here.
    state = state.forward_cfg_node()
    state = self._store_value(state, varname, new_var, local=True)
    state = state.forward_cfg_node()
    return state

  def _narrow(self, state, var, pred):
    """Narrow a variable by removing bindings that do not satisfy pred."""
    keep = [b for b in var.bindings if pred(b.data)]
    if len(keep) == len(var.bindings):
      # Nothing to narrow.
      return state
    out = self.ctx.program.NewVariable()
    for b in keep:
      out.AddBinding(b.data, {b}, state.node)
    return self._store_new_var_in_local(state, var, out)

  def _set_type_from_assert_isinstance(self, state, var, class_spec):
    # TODO(mdemello): If we want to cast var to typ via an assertion, should
    # we check that at least one binding of var is compatible with typ?
    classes = []
    abstract_utils.flatten(class_spec, classes)
    node, new_type = self.init_class(state.node,
                                     self.ctx.convert.merge_values(classes))
    state = state.change_cfg_node(node)
    return self._store_new_var_in_local(state, var, new_type)

  def _check_test_assert(self, state, func, args):
    """Narrow the types of variables based on test assertions."""
    # We need a variable to narrow
    if not args:
      return state
    var = args[0]
    f = func.data[0]
    if not isinstance(f, abstract.BoundFunction) or len(f.callself.data) != 1:
      return state
    cls = f.callself.data[0].cls
    if not (isinstance(cls, abstract.Class) and cls.is_test_class()):
      return state
    if f.name == "assertIsNotNone":
      if len(args) == 1:
        pred = lambda v: not self._data_is_none(v)
        state = self._narrow(state, var, pred)
    elif f.name == "assertIsInstance":
      if len(args) == 2:
        class_spec = args[1].data[0]
        state = self._set_type_from_assert_isinstance(state, var, class_spec)
    return state

  def byte_CALL_METHOD(self, state, op):
    state, args = state.popn(op.arg)
    state, func = state.pop()
    state, result = self.call_function_with_state(state, func, args)
    return state.push(result)

  def byte_RERAISE(self, state, op):
    del op  # unused
    state, _ = state.popn(3)
    return state.set_why("reraise")

  def byte_WITH_EXCEPT_START(self, state, op):
    del op  # unused
    func = state.peek(7)
    args = state.topn(3)
    state, result = self.call_function_with_state(state, func, args)
    return state.push(result)

  def byte_LOAD_ASSERTION_ERROR(self, state, op):
    del op  # unused
    assertion_error = self.ctx.convert.name_to_value("builtins.AssertionError")
    return state.push(assertion_error.to_variable(state.node))

  def byte_GET_LEN(self, state, op):
    del op
    var = state.top()
    elts = vm_utils.unpack_iterable(state.node, var, self.ctx)
    length = abstract.SequenceLength(elts, self.ctx)
    log.debug("get_len: %r", length)
    return state.push(length.instantiate(state.node))

  def byte_MATCH_MAPPING(self, state, op):
    del op
    obj_var = state.top()
    is_map = vm_utils.match_mapping(state.node, obj_var, self.ctx)
    ret = self.ctx.convert.bool_values[is_map]
    log.debug("match_mapping: %r", ret)
    return state.push(ret.to_variable(state.node))

  def byte_MATCH_SEQUENCE(self, state, op):
    del op
    obj_var = state.top()
    is_seq = vm_utils.match_sequence(obj_var)
    ret = self.ctx.convert.bool_values[is_seq]
    log.debug("match_sequence: %r", ret)
    return state.push(ret.to_variable(state.node))

  def byte_MATCH_KEYS(self, state, op):
    """Implementation of the MATCH_KEYS opcode."""
    del op
    obj_var, keys_var = state.topn(2)
    vals = vm_utils.match_keys(state.node, obj_var, keys_var, self.ctx)
    if vals:
      state = state.push(vals,
                         self.ctx.convert.true.to_variable(state.node))
    else:
      state = state.push(self.ctx.convert.none.to_variable(state.node),
                         self.ctx.convert.false.to_variable(state.node))
    return state

  def byte_MATCH_CLASS(self, state, op):
    """Implementation of the MATCH_CLASS opcode."""
    # NOTE: 3.10 specific; stack effects change somewhere en route to 3.12
    posarg_count = op.arg
    state, keys_var = state.pop()
    obj_var, cls_var = state.topn(2)
    ret = vm_utils.match_class(
        state.node, obj_var, cls_var, keys_var, posarg_count, self.ctx)
    state = state.set_top(
        self.ctx.convert.bool_values[ret.success].to_variable(state.node))
    if ret.values:
      state = state.set_second(ret.values)
    return state

  def byte_COPY_DICT_WITHOUT_KEYS(self, state, op):
    del op
    state, keys_var = state.pop()
    obj_var = state.top()
    ret = vm_utils.copy_dict_without_keys(
        state.node, obj_var, keys_var, self.ctx)
    return state.push(ret)

  def byte_GEN_START(self, state, op):
    del op
    return state.pop_and_discard()
