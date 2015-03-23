"""Functions for computing the execution order of bytecode.

This file aims to replace pycfg.py.
"""

from pytype import utils
from pytype.pyc import opcodes


class OrderedCode(object):
  """Code object which knows about instruction ordering.

  Attributes:
    co_*: Same as loadmarshal.Code.
    order: A list of bytecode blocks. They're ordered ancestors-first, see
      utils.py:order_nodes.
    python_version: The Python version this bytecode is from.
  """

  def __init__(self, code, order, python_version):
    # Copy all "co_*" attributes from code.
    # This is preferable to both inheritance (because we don't want to be
    # compatible with the base class, which is too low level) as well as
    # object composition (because that would make the API too clunky for
    # callers).
    self.__dict__.update({name: value for name, value in code.__dict__.items()
                          if name.startswith("co_")})
    self.order = order
    self.python_version = python_version


class Block(object):
  """A block is a node in a directed graph.

  It has incoming and outgoing edges (jumps). Incoming jumps always jump
  to the first instruction of our bytecode, and outgoing jumps always jump
  from the last instruction. There are no jump instructions in the middle of
  a byte code block.
  A block implements most of the "sequence" interface, i.e., it can be used as
  if it was a Python list of bytecode instructions.

  Attributes:
    code: A bytecode object (a list of instances of opcodes.Opcode).
    incoming: Incoming edges. These are blocks that jump to the first
      instruction in our code object.
    outgoing: Outgoing edges. These are the targets jumped to by the last
      instruction in our code object.
  """

  def __init__(self, code):
    self.id = code[0].index
    self.code = code
    self.incoming = set()
    self.outgoing = set()

  def connect_outgoing(self, target):
    """Add an outgoing edge."""
    self.outgoing.add(target)
    target.incoming.add(self)

  def __str__(self):
    return "<Block %d>" % self.id

  def __repr__(self):
    return "<Block %d: %r>" % (self.id, self.code)

  def __getitem__(self, index_or_slice):
    return self.code.__getitem__(index_or_slice)

  def __iter__(self):
    return self.code.__iter__()


def split_bytecode(bytecode):
  """Given a sequence of bytecodes, return basic blocks.

  This will split the code at "basic block boundaries". These occur at
  every instruction that is jumped to, and after every instruction that jumps
  somewhere else (or returns / aborts).

  Args:
    bytecode: A list of instances of opcodes.Opcode. (E.g. returned from
      opcodes.dis())

  Returns:
    A list of _Block instances.
  """
  targets = {op.target for op in bytecode if op.target}
  blocks = []
  code = []
  for op in bytecode:
    code.append(op)
    does_jump = op.has_jump() and not op.store_jump()
    if op.no_next() or does_jump or op.next is None or op.next in targets:
      blocks.append(Block(code))
      code = []
  return blocks


def compute_order(bytecode):
  """Split bytecode into blocks and order the blocks.

  This builds an "ancestor first" ordering of the basic blocks of the bytecode.

  Args:
    bytecode: A list of instances of opcodes.Opcode. (E.g. returned from
      opcodes.dis())

  Returns:
    A list of Block instances.
  """
  blocks = split_bytecode(bytecode)
  first_op_to_block = {block.code[0]: block for block in blocks}
  for i, block in enumerate(blocks):
    next_block = blocks[i + 1] if i < len(blocks) - 1 else None
    last_op = block.code[-1]
    if next_block and not last_op.no_next():
      block.connect_outgoing(next_block)
    if last_op.target:
      block.connect_outgoing(first_op_to_block[last_op.target])
  return utils.order_nodes(blocks)


def order_code(co):
  """Split a CodeType object into ordered blocks.

  This takes a CodeType object (i.e., a piece of compiled Python code) and
  splits it into ordered basic blocks.

  Args:
    co: A loadmarshal.CodeType object.

  Returns:
    A CodeBlocks instance.
  """
  bytecodes = opcodes.dis(data=co.co_code, python_version=co.python_version,
                          lines=co.co_lnotab, line_offset=co.co_firstlineno)
  return OrderedCode(co, compute_order(bytecodes), co.python_version)
