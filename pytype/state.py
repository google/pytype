"""Objects modelling VM state. (Frames etc.)."""

import collections
import logging


log = logging.getLogger(__name__)


FrameState = collections.namedtuple("FrameState", ["block_stack", "data_stack"])


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
    f_lasti: The instruction pointer. Despite its name (which matches actual
    python frames) this points to the next instruction that will be executed.
    block_stack: A stack of blocks used to manage exceptions, loops, and
    "with"s.
    data_stack: The value stack that is used for instruction operands.
    generator: None or a Generator object if this frame is a generator frame.
    cfgnode: A mapping from pycfg BasicBlocks to typegraph CFGNodes.
    return_nodes: A list of nodes that return from the function. This is used to
      connect the next node in the CFG properly.
    return_values: A set of (return value, location) pairs that will be merged
      to produce the actual return from this frame.
  """

  def __init__(self, vm, f_code, f_globals, f_locals, f_back, callargs,
               closure=None):
    """Initialize a special frame as needed by TypegraphVirtualMachine.

    Args:
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
    self.f_globals = f_globals
    self.f_locals = f_locals
    self.f_back = f_back
    if f_back:
      self.f_builtins = f_back.f_builtins
    else:
      builtins_pu, = f_globals.get_attribute("__builtins__").values
      self.f_builtins = builtins_pu.data
    self.f_lineno = f_code.co_firstlineno
    self.f_lasti = 0
    self.current_block = None
    self.cells = {}
    self.generator = None
    self.cfgnode = {}
    self.return_nodes = []
    self.return_variable = self.vm.program.NewVariable(
        "return(frame:" + f_code.co_name + ")")
    # The stack holding exception and generator handling information
    self.block_stack = []
    # The stack holding input and output of bytecode instructions
    self.data_stack = []

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
    log.info("co_cellvars: %r", f_code.co_cellvars)
    log.info("co_freevars: %r", f_code.co_freevars)
    self.cells = [self.vm.program.NewVariable(name)
                  for name in f_code.co_cellvars]
    self.cells.extend(closure or [])

    if callargs:
      for name, value in callargs.items():
        if name in f_code.co_cellvars:
          i = f_code.co_cellvars.index(name)
          self.cells[i].AddValues(value, self.vm.current_location)
        else:
          self.f_locals.set_attribute(name, value)

  def store_callargs(self, d):
    self.f_locals.update(d)

  def save_state(self):
    return FrameState(self.block_stack[:], self.data_stack[:])

  def restore_state(self, state):
    self.block_stack = state.block_stack[:]
    self.data_stack = state.data_stack[:]

  def push(self, *vals):
    """Push values onto the value stack."""
    self.data_stack.extend(vals)

  def __repr__(self):     # pragma: no cover
    return "<Frame at 0x%08x: %r @ %d>" % (
        id(self), self.f_code.co_filename, self.f_lineno
    )

  def line_number(self):
    """Get the current line number the frame is executing."""
    # TODO(kramm): Accodrding to pludemann@, line_number() sometimes has an
    #              off-by-one error.
    # We don't keep f_lineno up to date, so calculate it based on the
    # instruction address and the line number table.
    lnotab = self.f_code.co_lnotab
    byte_increments = map(ord, lnotab[0::2])
    line_increments = map(ord, lnotab[1::2])

    byte_num = 0
    line_num = self.f_code.co_firstlineno

    # TODO(pludemann): there might be a bug in this code -- it seems to have an
    #                  off-by-one error sometimes.  Also, see
    #                  pycfg.BlockTable.get_line() for a faster way (also
    #                  sometimes with an off-by-one error).
    for byte_incr, line_incr in zip(byte_increments, line_increments):
      byte_num += byte_incr
      if byte_num > self.f_lasti:
        break
      line_num += line_incr

    return line_num
