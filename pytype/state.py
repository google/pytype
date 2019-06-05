"""Objects modelling VM state. (Frames etc.)."""

import collections
import logging

from pytype import abstract
from pytype import compare
from pytype import metrics
from pytype import mixin
from pytype import utils
from pytype.typegraph import cfg

log = logging.getLogger(__name__)

# A special constant, returned by split_conditions() to signal that the
# condition cannot be satisfied with any known bindings.
UNSATISFIABLE = object()


class FrameState(utils.VirtualMachineWeakrefMixin):
  """Immutable state object, for attaching to opcodes."""

  __slots__ = ["block_stack", "data_stack", "node", "exception", "why"]

  def __init__(self, data_stack, block_stack, node, vm, exception, why):
    super(FrameState, self).__init__(vm)
    self.data_stack = data_stack
    self.block_stack = block_stack
    self.node = node
    self.exception = exception
    self.why = why

  @classmethod
  def init(cls, node, vm):
    return FrameState((), (), node, vm, False, None)

  def __setattribute__(self):
    raise AttributeError("States are immutable.")

  def set_why(self, why):
    return FrameState(self.data_stack,
                      self.block_stack,
                      self.node,
                      self.vm,
                      self.exception,
                      why)

  def push(self, *values):
    """Push value(s) onto the value stack."""
    return FrameState(self.data_stack + tuple(values),
                      self.block_stack,
                      self.node,
                      self.vm,
                      self.exception,
                      self.why)

  def peek(self, n):
    """Get a value `n` entries down in the stack, without changing the stack."""
    return self.data_stack[-n]

  def top(self):
    return self.data_stack[-1]

  def topn(self, n):
    if n > 0:
      return self.data_stack[-n:]
    else:
      return ()

  def pop(self):
    """Pop a value from the value stack."""
    value = self.data_stack[-1]
    return FrameState(self.data_stack[:-1],
                      self.block_stack,
                      self.node,
                      self.vm,
                      self.exception,
                      self.why), value

  def pop_and_discard(self):
    """Pop a value from the value stack and discard it."""
    return FrameState(self.data_stack[:-1],
                      self.block_stack,
                      self.node,
                      self.vm,
                      self.exception,
                      self.why)

  def popn(self, n):
    """Return n values, ordered oldest-to-newest."""
    if not n:
      # Not an error: E.g. function calls with no parameters pop zero items
      return self, ()
    if len(self.data_stack) < n:
      raise IndexError("Trying to pop %d values from stack of size %d" %
                       (n, len(self.data_stack)))
    values = self.data_stack[-n:]
    return FrameState(self.data_stack[:-n],
                      self.block_stack,
                      self.node,
                      self.vm,
                      self.exception,
                      self.why), values

  def push_block(self, block):
    """Push a block on to the block stack."""
    return FrameState(self.data_stack,
                      self.block_stack + (block,),
                      self.node,
                      self.vm,
                      self.exception,
                      self.why)

  def pop_block(self):
    """Pop a block from the block stack."""
    block = self.block_stack[-1]
    return FrameState(self.data_stack,
                      self.block_stack[:-1],
                      self.node,
                      self.vm,
                      self.exception,
                      self.why), block

  def change_cfg_node(self, node):
    assert isinstance(node, cfg.CFGNode)
    if self.node is node:
      return self
    return FrameState(self.data_stack,
                      self.block_stack,
                      node,
                      self.vm,
                      self.exception,
                      self.why)

  def connect_to_cfg_node(self, node):
    self.node.ConnectTo(node)
    return self.change_cfg_node(node)

  def forward_cfg_node(self, condition=None):
    """Create a new CFG Node connected to the current cfg node.

    Args:
      condition: A cfg.Binding representing the condition that needs to be true
        for this node to be reached.

    Returns:
      A new state which is the same as this state except for the node, which is
      the new one.
    """
    new_node = self.node.ConnectNew(self.vm.frame and
                                    self.vm.frame.current_opcode and
                                    self.vm.frame.current_opcode.line,
                                    condition)
    return self.change_cfg_node(new_node)

  def merge_into(self, other):
    """Merge with another state."""
    if other is None:
      return self
    assert len(self.data_stack) == len(other.data_stack)
    assert len(self.block_stack) == len(other.block_stack)
    node = other.node
    if self.node is not node:
      self.node.ConnectTo(node)
    both = list(zip(self.data_stack, other.data_stack))
    if any(v1 is not v2 for v1, v2 in both):
      for v, o in both:
        o.PasteVariable(v, None)
    if self.node is not other.node:
      self.node.ConnectTo(other.node)
      return FrameState(other.data_stack,
                        self.block_stack,
                        other.node,
                        self.vm,
                        self.exception,
                        self.why)
    return self

  def set_exception(self):
    return FrameState(self.data_stack,
                      self.block_stack,
                      self.node.ConnectNew(self.vm.frame.current_opcode.line),
                      self.vm,
                      True,
                      self.why)


class SimpleFrame(object):
  """A lightweight placeholder frame.

  A frame used when we need a placeholder on the stack, e.g., to imitate a
  function call in order to analyze a function, or to create a dummy stack for
  error logging.
  """

  def __init__(self, opcode=None, node=None):
    self.f_code = None  # for recursion detection
    self.f_builtins = None
    self.f_globals = None
    self.current_opcode = opcode  # for memoization of unknowns
    self.node = node


class Frame(utils.VirtualMachineWeakrefMixin):
  """An interpreter frame.

  This contains the local value and block stacks and the associated code and
  pointer. The most complex usage is with generators in which a frame is stored
  and then repeatedly reactivated. Other than that frames are created executed
  and then discarded.

  Attributes:
    f_code: The code object this frame is executing.
    f_globals: The globals dict used for global name resolution.
    f_locals: The locals used for name resolution. Will be modified by
      Frame.__init__ if callargs is passed.
    f_builtins: Similar for builtins.
    f_back: The frame above self on the stack.
    f_lineno: The first line number of the code object.
    vm: The VirtualMachine instance we belong to.
    node: The node at which the frame is created.
    states: A mapping from opcodes to FrameState objects.
    cells: local variables bound in a closure, or used in a closure.
    block_stack: A stack of blocks used to manage exceptions, loops, and
      "with"s.
    data_stack: The value stack that is used for instruction operands.
    allowed_returns: The return annotation of this function.
    check_return: Whether the actual return type of a call should be checked
      against allowed_returns.
    return_variable: The return value of this function, as a Variable.
    yield_variable: The yield value of this function, as a Variable.
  """

  def __init__(self, node, vm, f_code, f_globals, f_locals, f_back, callargs,
               closure, func, first_posarg=None):
    """Initialize a special frame as needed by TypegraphVirtualMachine.

    Args:
      node: The current CFG graph node.
      vm: The owning virtual machine.
      f_code: The code object to execute in this frame.
      f_globals: The global context to execute in as a SimpleAbstractValue as
        used by TypegraphVirtualMachine.
      f_locals: Local variables. Will be modified if callargs is passed.
      f_back: The frame above this one on the stack.
      callargs: Additional function arguments to store in f_locals.
      closure: A tuple containing the new co_freevars.
      func: An Optional[cfg.Binding] to the function this frame corresponds to.
      first_posarg: Optional first positional argument to the function.
    Raises:
      NameError: If we can't resolve any references into the outer frame.
    """
    super(Frame, self).__init__(vm)
    assert isinstance(f_globals, abstract.LazyConcreteDict)
    assert isinstance(f_locals, abstract.LazyConcreteDict)
    self.node = node
    self.current_opcode = None
    self.f_code = f_code
    self.states = {}
    self.f_globals = f_globals
    self.f_locals = f_locals
    self.f_back = f_back
    if f_back and f_back.f_builtins:
      self.f_builtins = f_back.f_builtins
    else:
      _, bltin = self.vm.attribute_handler.get_attribute(
          self.vm.root_cfg_node, f_globals, "__builtins__")
      builtins_pu, = bltin.bindings
      self.f_builtins = builtins_pu.data
    self.f_lineno = f_code.co_firstlineno
    # The first positional argument is used to make Python 3 super calls
    # when super is not passed any arguments.
    self.first_posarg = first_posarg
    self.cells = {}

    self.allowed_returns = None
    self.check_return = False
    self.return_variable = self.vm.program.NewVariable()
    self.yield_variable = self.vm.program.NewVariable()

    # A map from function name to @typing.overload-decorated signatures. The
    # overloads are copied to the implementation in InterpreterFunction.make.
    self.overloads = collections.defaultdict(list)

    # A closure g communicates with its outer function f through two
    # fields in CodeType (both of which are tuples of strings):
    # f.co_cellvars: All f-local variables that are used in g (or any other
    #                closure).
    # g.co_freevars: All variables from f that g uses.
    # Also, note that f.co_cellvars will only also be in f.co_varnames
    # if they are also parameters of f (because co_varnames[0:co_argcount] are
    # always the parameters), but won't otherwise.
    # Cells 0 .. num(cellvars)-1 : cellvar; num(cellvars) .. end : freevar
    assert len(f_code.co_freevars) == len(closure or [])
    self.cells = [self.vm.program.NewVariable()
                  for _ in f_code.co_cellvars]
    self.cells.extend(closure or [])

    if callargs:
      for name, value in sorted(callargs.items()):
        if name in f_code.co_cellvars:
          i = f_code.co_cellvars.index(name)
          self.cells[i].PasteVariable(value, node)
        else:
          self.vm.attribute_handler.set_attribute(node, f_locals, name, value)
    # Python 3 supports calling 'super' without any arguments. In such a case
    # the implicit type argument is inserted into __build_class__'s cellvars
    # and propagated as a closure variable to all method/functions calling
    # 'super' without any arguments.
    # If this is a frame for the function called by __build_class__ (see
    # abstract.BuildClass), then we will store a reference to the variable
    # corresponding to the cellvar named "__class__" separately for convenient
    # access. After the class is built, abstract.BuildClass.call will add the
    # binding for the new class into this variable.
    self.class_closure_var = None
    if func and isinstance(func.data, abstract.InterpreterFunction):
      closure_name = abstract.BuildClass.CLOSURE_NAME
      if func.data.is_class_builder and closure_name in f_code.co_cellvars:
        i = f_code.co_cellvars.index(closure_name)
        self.class_closure_var = self.cells[i]
    self.func = func

  def __repr__(self):     # pragma: no cover
    return "<Frame at 0x%08x: %r @ %d>" % (
        id(self), self.f_code.co_filename, self.f_lineno
    )


class Condition(object):
  """Represents a condition due to if-splitting.

  Properties:
    node: A CFGNode.
    binding: A Binding for the condition's constraints.
  """

  def __init__(self, node, dnf):
    # The condition is represented by a dummy variable with a single binding
    # to None.  The origins for this binding are the dnf clauses.
    self._var = node.program.NewVariable()
    self._binding = self._var.AddBinding(None)
    for clause in dnf:
      sources = set(clause)
      self._binding.AddOrigin(node, sources)

  @property
  def binding(self):
    return self._binding


_restrict_counter = metrics.MapCounter("state_restrict")


def split_conditions(node, var):
  """Return a pair of conditions for the value being true and false."""
  return (_restrict_condition(node, var.bindings, True),
          _restrict_condition(node, var.bindings, False))


def _restrict_condition(node, bindings, logical_value):
  """Return a restricted condition based on filtered bindings.

  Args:
    node: The CFGNode.
    bindings: A sequence of bindings.
    logical_value: Either True or False.

  Returns:
    A Condition or None.  Each binding is checked for compatibility with
    logical_value.  If either no bindings match, or all bindings match, then
    None is returned.  Otherwise a new Condition is built from the specified,
    compatible, bindings.
  """
  dnf = []
  restricted = False
  for b in bindings:
    match = compare.compatible_with(b.data, logical_value)
    if match is True:  # pylint: disable=g-bool-id-comparison
      dnf.append([b])
    elif match is False:  # pylint: disable=g-bool-id-comparison
      restricted = True
    else:
      dnf.extend(match)
      # In theory, the value could have returned [[b]] as its DNF, in which
      # case this isn't really a restriction.  However in practice this is
      # very unlikely to occur, and treating it as a restriction will not
      # cause any problems.
      restricted = True
  if not dnf:
    _restrict_counter.inc("unsatisfiable")
    return UNSATISFIABLE
  elif restricted:
    _restrict_counter.inc("restricted")
    return Condition(node, dnf)
  else:
    _restrict_counter.inc("unrestricted")
    return None


def _is_or_is_not_cmp(left, right, is_not=False):
  """Implementation of 'left is right' amd 'left is not right'."""
  if (isinstance(left, mixin.PythonConstant) and
      isinstance(right, mixin.PythonConstant)):
    if left.cls != right.cls:
      return is_not
    return is_not ^ (left.pyval == right.pyval)
  elif (isinstance(left, abstract.Instance) and
        isinstance(right, abstract.Instance)):
    if left.cls != right.cls:
      # If those were the same they could be the same but we can't be sure from
      # comparing types.
      return is_not
    return None
  elif isinstance(left, mixin.Class) and isinstance(right, mixin.Class):
    # types are singletons. We use the name so that, e.g., two different
    # TupleClass instances compare as identical.
    return is_not ^ (left.full_name == right.full_name)
  else:
    return None


def is_cmp(left, right):
  return _is_or_is_not_cmp(left, right, is_not=False)


def is_not_cmp(left, right):
  return _is_or_is_not_cmp(left, right, is_not=True)
