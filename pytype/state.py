"""Objects modelling VM state. (Frames etc.)."""

import logging


from pytype import abstract
from pytype import metrics
from pytype.pytd import cfg

log = logging.getLogger(__name__)

# A special constant, returned by split_conditions() to signal that the
# condition cannot be satisfied with any known bindings.
UNSATISFIABLE = object()


class FrameState(object):
  """Immutable state object, for attaching to opcodes."""

  __slots__ = ["block_stack", "data_stack", "node", "exception", "why",
               "condition"]

  def __init__(self, data_stack, block_stack, node, exception, why,
               condition=None):
    self.data_stack = data_stack
    self.block_stack = block_stack
    self.node = node
    self.exception = exception
    self.why = why
    self.condition = condition

  @classmethod
  def init(cls, node):
    return FrameState((), (), node, None, None, None)

  def __setattribute__(self):
    raise AttributeError("States are immutable.")

  def set_why(self, why):
    return FrameState(self.data_stack,
                      self.block_stack,
                      self.node,
                      self.exception,
                      why,
                      self.condition)

  def set_condition(self, condition):
    return FrameState(self.data_stack,
                      self.block_stack,
                      self.node,
                      self.exception,
                      self.why,
                      condition)

  def push(self, *values):
    """Push value(s) onto the value stack."""
    return FrameState(self.data_stack + tuple(values),
                      self.block_stack,
                      self.node,
                      self.exception,
                      self.why,
                      self.condition)

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
                      self.exception,
                      self.why,
                      self.condition), value

  def pop_and_discard(self):
    """Pop a value from the value stack and discard it."""
    return FrameState(self.data_stack[:-1],
                      self.block_stack,
                      self.node,
                      self.exception,
                      self.why,
                      self.condition)

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
                      self.exception,
                      self.why,
                      self.condition), values

  def push_block(self, block):
    """Push a block on to the block stack."""
    return FrameState(self.data_stack,
                      self.block_stack + (block,),
                      self.node,
                      self.exception,
                      self.why,
                      self.condition)

  def pop_block(self):
    """Pop a block from the block stack."""
    block = self.block_stack[-1]
    return FrameState(self.data_stack,
                      self.block_stack[:-1],
                      self.node,
                      self.exception,
                      self.why,
                      self.condition), block

  def change_cfg_node(self, node):
    assert isinstance(node, cfg.CFGNode)
    if self.node is node:
      return self
    return FrameState(self.data_stack,
                      self.block_stack,
                      node,
                      self.exception,
                      self.why,
                      self.condition)

  def connect_to_cfg_node(self, node):
    self.node.ConnectTo(node)
    return self.change_cfg_node(node)

  def forward_cfg_node(self):
    new_node = self.node.ConnectNew(self.node.name)
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
    both = zip(self.data_stack, other.data_stack)
    if all(v1 is v2 for v1, v2 in both):
      data_stack = self.data_stack
    else:
      data_stack = tuple(
          self.node.program.MergeVariables(node, "stack%d" % i, [v1, v2])
          for i, (v1, v2) in enumerate(both))
    if self.node is not other.node:
      self.node.ConnectTo(other.node)
      return FrameState(data_stack,
                        self.block_stack,
                        other.node,
                        self.exception,
                        self.why,
                        _common_condition(self.condition, other.condition))
    return self

  def set_exception(self, exc_type, value, tb):
    return FrameState(self.data_stack,
                      self.block_stack,
                      self.node.ConnectNew(self.node.name),
                      (exc_type, value, tb),
                      self.why,
                      self.condition)


class Frame(object):
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
    states: A mapping from opcodes to FrameState objects.
    cells: local variables bound in a closure, or used in a closure.
    block_stack: A stack of blocks used to manage exceptions, loops, and
    "with"s.
    data_stack: The value stack that is used for instruction operands.
    generator: None or a Generator object if this frame is a generator frame.
    allowed_returns: The return annotation of this function.
    return_variable: The return value of this function, as a Variable.
    yield_variable: The yield value of this function, as a Variable.
  """

  def __init__(self, node, vm, f_code, f_globals, f_locals, f_back, callargs,
               closure=None):
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
    Raises:
      NameError: If we can't resolve any references into the outer frame.
    """
    assert isinstance(f_globals, abstract.LazyAbstractOrConcreteValue)
    assert isinstance(f_locals, abstract.LazyAbstractOrConcreteValue)
    self.vm = vm
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
    self.cells = {}

    self.allowed_returns = None
    self.return_variable = self.vm.program.NewVariable(
        "return(frame:" + f_code.co_name + ")")
    self.yield_variable = self.vm.program.NewVariable("yield")

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
    self.cells = [self.vm.program.NewVariable(name)
                  for name in f_code.co_cellvars]
    self.cells.extend(closure or [])

    if callargs:
      for name, value in sorted(callargs.items()):
        if name in f_code.co_cellvars:
          i = f_code.co_cellvars.index(name)
          self.cells[i].PasteVariable(value, node)
        else:
          self.vm.attribute_handler.set_attribute(node, f_locals, name, value)

  def __repr__(self):     # pragma: no cover
    return "<Frame at 0x%08x: %r @ %d>" % (
        id(self), self.f_code.co_filename, self.f_lineno
    )


class Condition(object):
  """Represents a condition due to if-splitting.

  Properties:
    node: A CFGNode.
    parent: The parent Condition (or None).
    binding: A Binding for the condition's constraints.
  """

  def __init__(self, node, parent, dnf):
    self._parent = parent
    # The condition is represented by a dummy variable with a single binding
    # to None.  The origins for this binding are the dnf clauses with the
    # addition of the parent's binding.
    self._var = node.program.NewVariable("__split")
    self._binding = self._var.AddBinding(None)
    for clause in dnf:
      sources = set(clause)
      if parent:
        sources.add(parent.binding)
      self._binding.AddOrigin(node, sources)

  @property
  def parent(self):
    return self._parent

  @property
  def binding(self):
    return self._binding


_restrict_counter = metrics.MapCounter("state_restrict")


def split_conditions(node, parent, var):
  """Return a pair of conditions for the value being true and false."""
  return (_restrict_condition(node, parent, var.bindings, True),
          _restrict_condition(node, parent, var.bindings, False))


def _restrict_condition(node, parent, bindings, logical_value):
  """Return a restricted condition based on a parent and filtered bindings.

  Args:
    node: The CFGNode.
    parent: A parent Condition or None.
    bindings: A sequence of bindings.
    logical_value: Either True or False.

  Returns:
    A Condition or None.  Each binding is checked for compatability with
    logical_value.  If either no bindings match, or all bindings match, then
    parent is returned.  Otherwise a new Condition is built from the specified
    parent and the compatible bindings.
  """
  dnf = []
  restricted = False
  for b in bindings:
    match = b.data.compatible_with(logical_value)
    if match is True:
      dnf.append([b])
    elif match is False:
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
    return Condition(node, parent, dnf)
  else:
    _restrict_counter.inc("unrestricted")
    return parent


def _transitive_conditions(condition):
  """Return the transitive closure of a condition and its ancestors."""
  transitive = set()
  while condition:
    transitive.add(condition)
    condition = condition.parent
  return transitive


def _common_condition(cond1, cond2):
  """Return the closest common ancestor of two conditions."""
  # If either condition is None, then return None.
  if cond1 is None or cond2 is None:
    return None

  # Determine the transitive closures of the two conditions.
  common = (_transitive_conditions(cond1) &
            _transitive_conditions(cond2))

  # Walk up each tree until reaching a condition that is common.
  while cond1 and cond1 not in common:
    cond1 = cond1.parent
  while cond2 and cond2 not in common:
    cond2 = cond2.parent

  # We should get the same answer from both sides.
  assert cond1 == cond2
  return cond1


def _is_or_is_not_cmp(left, right, is_not=False):
  if (not isinstance(left, abstract.PythonConstant) or
      not isinstance(right, abstract.PythonConstant)):
    return None

  if left.cls != right.cls:
    return is_not

  return is_not ^ (left.pyval == right.pyval)


def is_cmp(left, right):
  return _is_or_is_not_cmp(left, right, is_not=False)


def is_not_cmp(left, right):
  return _is_or_is_not_cmp(left, right, is_not=True)
