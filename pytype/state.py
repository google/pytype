"""Objects modelling VM state. (Frames etc.)."""

import logging


from pytype.pytd import cfg

log = logging.getLogger(__name__)


class FrameState(object):
  """Immutable state object, for attaching to opcodes."""

  __slots__ = ["block_stack", "data_stack", "node", "exception", "why"]

  def __init__(self, data_stack, block_stack, node, exception, why):
    self.data_stack = data_stack
    self.block_stack = block_stack
    self.node = node
    self.exception = exception
    self.why = why

  @classmethod
  def init(cls, node):
    return FrameState((), (), node, None, None)

  def __setattribute__(self):
    raise AttributeError("States are immutable.")

  def set_why(self, why):
    return FrameState(self.data_stack,
                      self.block_stack,
                      self.node,
                      self.exception,
                      why)

  def push(self, *values):
    """Push value(s) onto the value stack."""
    return FrameState(self.data_stack + tuple(values),
                      self.block_stack,
                      self.node,
                      self.exception,
                      self.why)

  def peek(self, n):
    """Get a value `n` entries down in the stack, without changing the stack."""
    return self.data_stack[-n]

  def top(self):
    return self.data_stack[-1]

  def pop(self):
    """Pop a value from the value stack."""
    value = self.data_stack[-1]
    return FrameState(self.data_stack[:-1],
                      self.block_stack,
                      self.node,
                      self.exception,
                      self.why), value

  def pop_and_discard(self):
    """Pop a value from the value stack and discard it."""
    return FrameState(self.data_stack[:-1],
                      self.block_stack,
                      self.node,
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
                      self.exception,
                      self.why), values

  def push_block(self, block):
    """Push a block on to the block stack."""
    return FrameState(self.data_stack,
                      self.block_stack + (block,),
                      self.node,
                      self.exception,
                      self.why)

  def pop_block(self):
    """Pop a block from the block stack."""
    block = self.block_stack[-1]
    return FrameState(self.data_stack,
                      self.block_stack[:-1],
                      self.node,
                      self.exception,
                      self.why), block

  def change_cfg_node(self, node):
    assert isinstance(node, cfg.CFGNode)
    if self.node is node:
      return self
    return FrameState(self.data_stack,
                      self.block_stack,
                      node,
                      self.exception,
                      self.why)

  def connect_to_cfg_node(self, node):
    self.node.ConnectTo(node)
    return self.change_cfg_node(node)

  def forward_cfg_node(self):
    new_node = self.node.ConnectNew()
    return self.change_cfg_node(new_node)

  def advance_cfg_node(self):
    return FrameState(self.data_stack,
                      self.block_stack,
                      self.node.ConnectNew(self.node.name),
                      self.exception,
                      self.why)

  def merge_into(self, other):
    """Merge with another state."""
    if other is None:
      return self
    assert len(self.data_stack) == len(other.data_stack)
    assert len(self.block_stack) == len(other.block_stack)
    if self.node is not other.node:
      self.node.ConnectTo(other.node)
      return FrameState(self.data_stack,
                        self.block_stack,
                        other.node,
                        self.exception,
                        self.why)
    # TODO(kramm): Also merge data stack
    return self

  def set_exception(self, exc_type, value, tb):
    return FrameState(self.data_stack,
                      self.block_stack,
                      self.node.ConnectNew(self.node.name),
                      (exc_type, value, tb),
                      self.why)


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
    return_nodes: A list of nodes that return from the function. This is used to
      connect the next node in the CFG properly.
    return_values: A set of (return value, location) pairs that will be merged
      to produce the actual return from this frame.
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
    self.vm = vm
    self.f_code = f_code
    self.states = {}
    self.f_globals = f_globals
    self.f_locals = f_locals
    self.f_back = f_back
    if f_back and f_back.f_builtins:
      self.f_builtins = f_back.f_builtins
    else:
      _, bltin = f_globals.get_attribute(None, "__builtins__")
      builtins_pu, = bltin.values
      self.f_builtins = builtins_pu.data
    self.f_lineno = f_code.co_firstlineno
    self.cells = {}
    self.generator = None

    self.return_variable = self.vm.program.NewVariable(
        "return(frame:" + f_code.co_name + ")")

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
          self.cells[i].AddValues(value, node)
        else:
          self.f_locals.set_attribute(node, name, value)

  def __repr__(self):     # pragma: no cover
    return "<Frame at 0x%08x: %r @ %d>" % (
        id(self), self.f_code.co_filename, self.f_lineno
    )
