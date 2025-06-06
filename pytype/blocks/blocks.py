"""Functions for computing the execution order of bytecode."""

from collections.abc import Iterator
from typing import Any, Sequence, cast
from pycnite import bytecode as pyc_bytecode
from pycnite import marshal as pyc_marshal
import pycnite.types
from pytype.pyc import opcodes
from pytype.typegraph import cfg_utils
from typing_extensions import Self

STORE_OPCODES = (
    opcodes.STORE_NAME,
    opcodes.STORE_FAST,
    opcodes.STORE_ATTR,
    opcodes.STORE_DEREF,
    opcodes.STORE_GLOBAL,
)

_NOOP_OPCODES = (opcodes.NOP, opcodes.PRECALL, opcodes.RESUME)


class _Locals311:
  """Unpack the code.co_localsplus* attributes in 3.11+."""

  # Cell kinds (cpython/Include/internal/pycore_code.h)
  CO_FAST_LOCAL = 0x20
  CO_FAST_CELL = 0x40
  CO_FAST_FREE = 0x80

  def __init__(self, code: pycnite.types.CodeType311):
    table = list(zip(code.co_localsplusnames, code.co_localspluskinds))
    filter_names = lambda k: tuple(name for name, kind in table if kind & k)
    self.co_varnames = filter_names(self.CO_FAST_LOCAL)
    self.co_cellvars = filter_names(self.CO_FAST_CELL)
    self.co_freevars = filter_names(self.CO_FAST_FREE)
    self.localsplus = code.co_localsplusnames


class Block:
  """A block is a node in a directed graph.

  It has incoming and outgoing edges (jumps). Incoming jumps always jump
  to the first instruction of our bytecode, and outgoing jumps always jump
  from the last instruction. There are no jump instructions in the middle of
  a byte code block.
  A block implements most of the "sequence" interface, i.e., it can be used as
  if it was a Python list of bytecode instructions.

  Attributes:
    id: Block id
    code: A bytecode object (a list of instances of opcodes.Opcode).
    incoming: Incoming edges. These are blocks that jump to the first
      instruction in our code object.
    outgoing: Outgoing edges. These are the targets jumped to by the last
      instruction in our code object.
  """

  def __init__(self, code: list[opcodes.Opcode]):
    self.id = code[0].index
    self.code = code
    self.incoming: set[Self] = set()
    self.outgoing: set[Self] = set()

  def connect_outgoing(self, target: Self):
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


class OrderedCode:
  """Code object which knows about instruction ordering.

  Attributes:
    filename: Filename of the current module
    name: Code name (e.g. function name, <lambda>, etc.)
    qualname: The fully qualified code name in 3.11+
    consts: Tuple of code constants
    co_consts: Alias for consts
    names: Tuple of names of global variables used in the code
    varnames: Tuple of names of args and local variables
    argcount: Number of args
    posonlyargcount: Number of posonly args
    kwonlyargcount: Number of kwonly args
    firstlineno: The first line number of the code
    freevars: Tuple of free variable names
    cellvars: Tuple of cell variable names
    localsplus: Tuple of local variable names in 3.11+
    order: A list of bytecode blocks, ordered ancestors-first (See
      cfg_utils.py:order_nodes)
    code_iter: A flattened list of block opcodes. Corresponds to co_code.
    first_opcode: The first opcode in code_iter.
    exception_table: The exception table (for python 3.11+)
    python_version: The Python version this bytecode is from.
  """

  name: str
  qualname: str | None
  filename: bytes | str
  consts: tuple[Any, ...]
  names: tuple[str, ...]
  argcount: int
  posonlyargcount: int
  kwonlyargcount: int
  varnames: tuple[str, ...]
  cellvars: tuple[str, ...]
  freevars: tuple[str, ...]
  localsplus: tuple[str, ...]
  exception_table: tuple[Any, ...]
  order: list[Block]
  python_version: tuple[int, int]

  def __init__(
      self,
      code: pycnite.types.CodeTypeBase,
      bytecode: list[opcodes.Opcode],
      order: list[Block],
  ):
    assert hasattr(code, "co_code")
    self.name = code.co_name
    self.filename = code.co_filename
    self.consts = tuple(code.co_consts)
    self.names = tuple(code.co_names)
    self.argcount = code.co_argcount
    self.posonlyargcount = max(code.co_posonlyargcount, 0)
    self.kwonlyargcount = max(code.co_kwonlyargcount, 0)
    self.firstlineno = code.co_firstlineno
    if code.python_version >= (3, 11):
      code = cast(pycnite.types.CodeType311, code)
      self.qualname = code.co_qualname
      localsplus = _Locals311(code)
      self.varnames = tuple(localsplus.co_varnames)
      self.cellvars = tuple(localsplus.co_cellvars)
      self.freevars = tuple(localsplus.co_freevars)
      self.localsplus = tuple(localsplus.localsplus)
      self.exception_table = tuple(code.co_exceptiontable)
      combined_vars = self.localsplus
    else:
      code = cast(pycnite.types.CodeType38, code)
      self.qualname = None
      self.varnames = tuple(code.co_varnames)
      self.cellvars = tuple(code.co_cellvars)
      self.freevars = tuple(code.co_freevars)
      self.localsplus = ()
      self.exception_table = ()
      combined_vars = self.cellvars + self.freevars
    self._combined_vars = {name: i for (i, name) in enumerate(combined_vars)}
    # Retain the co_ name since this refers directly to CodeType internals.
    self._co_flags = code.co_flags
    self.order = order
    self.python_version = code.python_version
    for insn in bytecode:
      insn.code = self

  def __repr__(self):
    return f"OrderedCode({self.qualname}, version={self.python_version})"

  @property
  def co_consts(self):
    # The blocks/pyc code mixes CodeType and OrderedCode objects when
    # recursively iterating over code objects, so we need this accessor until
    # that is fixed.
    return self.consts

  @property
  def code_iter(self) -> Iterator[opcodes.Opcode]:
    return (op for block in self.order for op in block)  # pylint: disable=g-complex-comprehension

  def get_first_opcode(self, skip_noop=False):
    for op in self.code_iter:
      if not skip_noop or not isinstance(op, _NOOP_OPCODES):
        return op
    assert False, "OrderedCode should have at least one opcode"

  def has_opcode(self, op_type):
    return any(isinstance(op, op_type) for op in self.code_iter)

  def has_iterable_coroutine(self):
    return bool(self._co_flags & pyc_marshal.Flags.CO_ITERABLE_COROUTINE)

  def set_iterable_coroutine(self):
    self._co_flags |= pyc_marshal.Flags.CO_ITERABLE_COROUTINE

  def has_coroutine(self):
    return bool(self._co_flags & pyc_marshal.Flags.CO_COROUTINE)

  def has_generator(self):
    return bool(self._co_flags & pyc_marshal.Flags.CO_GENERATOR)

  def has_async_generator(self):
    return bool(self._co_flags & pyc_marshal.Flags.CO_ASYNC_GENERATOR)

  def has_varargs(self):
    return bool(self._co_flags & pyc_marshal.Flags.CO_VARARGS)

  def has_varkeywords(self):
    return bool(self._co_flags & pyc_marshal.Flags.CO_VARKEYWORDS)

  def has_newlocals(self):
    return bool(self._co_flags & pyc_marshal.Flags.CO_NEWLOCALS)

  def get_arg_count(self):
    """Total number of arg names including '*args' and '**kwargs'."""
    count = self.argcount + self.kwonlyargcount
    if self.has_varargs():
      count += 1
    if self.has_varkeywords():
      count += 1
    return count

  def get_cell_index(self, name):
    """Get the index of name in the code frame's cell list."""
    return self._combined_vars[name]


class BlockGraph:
  """CFG made up of ordered code blocks."""

  def __init__(self):
    self.graph: dict[opcodes.Opcode, OrderedCode] = {}

  def add(self, ordered_code: OrderedCode):
    self.graph[ordered_code.get_first_opcode()] = ordered_code

  def pretty_print(self):
    return str(self.graph)


def add_pop_block_targets(bytecode: list[opcodes.Opcode]) -> None:
  """Modifies bytecode so that each POP_BLOCK has a block_target.

  This is to achieve better initial ordering of try/except and try/finally code.
  try:
    i = 1
    a[i]
  except IndexError:
    return i
  By connecting a CFG edge from the end of the block (after the "a[i]") to the
  except handler, our basic block ordering algorithm knows that the except block
  needs to be scheduled last, whereas if there only was an edge before the
  "i = 1", it would be able to schedule it too early and thus encounter an
  undefined variable. This is only for ordering. The actual analysis of the
  code happens later, in vm.py.

  Args:
    bytecode: An array of bytecodes.
  """
  if not bytecode:
    return

  for op in bytecode:
    op.block_target = None

  setup_except_op = (opcodes.SETUP_FINALLY, opcodes.SETUP_EXCEPT_311)
  todo = [(bytecode[0], ())]  # unordered queue of (position, block_stack)
  seen = set()
  while todo:
    op, block_stack = todo.pop()
    if op in seen:
      continue
    else:
      seen.add(op)

    # Compute the block stack
    if isinstance(op, opcodes.POP_BLOCK):
      assert block_stack, "POP_BLOCK without block."
      op.block_target = block_stack[-1].target
      block_stack = block_stack[0:-1]
    elif isinstance(op, opcodes.RAISE_VARARGS):
      # Make "raise" statements jump to the innermost exception handler.
      # (If there's no exception handler, do nothing.)
      for b in reversed(block_stack):
        if isinstance(b, setup_except_op):
          op.block_target = b.target
          break
    elif isinstance(op, opcodes.BREAK_LOOP):
      # Breaks jump to after the loop
      for i in reversed(range(len(block_stack))):
        b = block_stack[i]
        if isinstance(b, opcodes.SETUP_LOOP):
          op.block_target = b.target
          assert b.target != op
          todo.append((op.block_target, block_stack[0:i]))
          break
    elif isinstance(op, setup_except_op):
      # Exceptions pop the block, so store the previous block stack.
      todo.append((op.target, block_stack))
      block_stack += (op,)
    elif op.pushes_block():
      assert op.target, f"{op.name} without target"
      # We push the entire opcode onto the block stack, for better debugging.
      block_stack += (op,)
    elif op.does_jump() and op.target:
      if op.push_exc_block:
        # We're jumping into an exception range, so push onto the block stack.
        setup_op = op.target
        while not isinstance(setup_op, setup_except_op):
          setup_op = setup_op.prev
        block_stack += (setup_op,)
      todo.append((op.target, block_stack))

    if not op.no_next():
      assert op.next, f"Bad instruction at end of bytecode: {op!r}."
      todo.append((op.next, block_stack))


def _split_bytecode(
    bytecode: list[opcodes.Opcode], processed_blocks: set[Block], python_version
) -> list[Block]:
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
  prev_block: Block = None
  i = 0
  while i < len(bytecode):
    op = bytecode[i]
    # SEND is only used in the context of async for and `yield from`.
    # These instructions are not used in other context, so it's safe to process
    # it assuming that these are the only constructs they're being used.
    if python_version >= (3, 12) and isinstance(op, opcodes.SEND):
      if code:
        prev_block = Block(code)
        blocks.append(prev_block)
        code = []
      new_blocks, i = _preprocess_async_for_and_yield(
          i, bytecode, prev_block, processed_blocks
      )
      blocks.extend(new_blocks)
      prev_block = blocks[-1]
      continue

    code.append(op)
    if (
        op.no_next()
        or op.does_jump()
        or op.pops_block()
        or op.next is None
        or (op.next in targets)
        and (
            not isinstance(op.next, opcodes.GET_ANEXT)
            or python_version < (3, 12)
        )
    ):
      prev_block = Block(code)
      blocks.append(prev_block)
      code = []
    i += 1

  return blocks


def _preprocess_async_for_and_yield(
    idx: int,
    bytecode: Sequence[opcodes.Opcode],
    prev_block: Block,
    processed_blocks: set[Block],
) -> tuple[list[Block], int]:
  """Process bytecode instructions for yield and async for in a way that pytype can iterate correctly.

  'Async for' and yield statements, contains instructions that starts with SEND
  and ends with END_SEND.

  The reason why we need to pre process async for is because the control flow of
  async for is drastically different from regular control flows also due to the
  fact that the termination of the loop happens by STOP_ASYNC_ITERATION
  exception, not a regular control flow. So we need to split (or merge) the
  basic blocks in a way that pytype executes in the order that what'd happen in
  the runtime, so that it doesn't fail with wrong order of execution, which can
  result in a stack underrun.

  Args:
    idx: The index of the SEND instruction.
    bytecode: A list of instances of opcodes.Opcode
    prev_block: The previous block that we want to connect the new blocks to.
    processed_blocks: Blocks that has been processed so that it doesn't get
      processed again by compute_order.

  Returns:
    A tuple of (list[Block], int), where the Block is the block containing the
    iteration part of the async for construct, and the int is the index of the
    END_SEND instruction.
  """
  assert isinstance(bytecode[idx], opcodes.SEND)
  i = next(
      i
      for i in range(idx + 1, len(bytecode))
      if isinstance(bytecode[i], opcodes.JUMP_BACKWARD_NO_INTERRUPT)
  )

  end_block_idx = i + 1
  # In CLEANUP_THROW can be present after JUMP_BACKWARD_NO_INTERRUPT
  # depending on how the control flow graph is constructed.
  # Usually, CLEANUP_THROW comes way after
  if isinstance(bytecode[end_block_idx], opcodes.CLEANUP_THROW):
    end_block_idx += 1

  # Somehow pytype expects the SEND and YIELD_VALUE to be in different
  # blocks, so we need to split.
  send_block = Block(bytecode[idx : idx + 1])
  yield_value_block = Block(bytecode[idx + 1 : end_block_idx])
  prev_block.connect_outgoing(send_block)
  send_block.connect_outgoing(yield_value_block)
  processed_blocks.update(send_block, yield_value_block)
  return [send_block, yield_value_block], end_block_idx


def _remove_jmp_to_get_anext_and_merge(
    blocks: list[Block], processed_blocks: set[Block]
) -> list[Block]:
  """Remove JUMP_BACKWARD instructions to GET_ANEXT instructions.

  And also merge the block that contains the END_ASYNC_FOR which is part of the
  same loop of the GET_ANEXT and JUMP_BACKWARD construct, to the JUMP_BACKWARD
  instruction. This is to ignore the JUMP_BACKWARD because in pytype's eyes it's
  useless (as it'll jump back to block that it already executed), and also
  this is the way to make pytype run the code of END_ASYNC_FOR and whatever
  comes afterwards.

  Args:
    blocks: A list of Block instances.

  Returns:
    A list of Block instances after the removal and merge.
  """
  op_to_block = {}
  merge_list = []
  for block_idx, block in enumerate(blocks):
    for code in block.code:
      op_to_block[code] = block_idx

  for block_idx, block in enumerate(blocks):
    for code in block.code:
      if code.end_async_for_target:
        merge_list.append((block_idx, op_to_block[code.end_async_for_target]))
  map_target = {}
  for block_idx, block_idx_to_merge in merge_list:
    # Remove JUMP_BACKWARD instruction as we don't want to execute it.
    jump_back_op = blocks[block_idx].code.pop()
    blocks[block_idx].code.extend(blocks[block_idx_to_merge].code)
    map_target[jump_back_op] = blocks[block_idx_to_merge].code[0]

    if block_idx_to_merge < len(blocks) - 1:
      blocks[block_idx].connect_outgoing(blocks[block_idx_to_merge + 1])
    processed_blocks.add(blocks[block_idx])

  to_delete = sorted({to_idx for _, to_idx in merge_list}, reverse=True)

  for block_idx in to_delete:
    del blocks[block_idx]

  for block in blocks:
    replace_op = map_target.get(block.code[-1].target, None)
    if replace_op:
      block.code[-1].target = replace_op

  return blocks


def _remove_jump_back_block(blocks: list[Block]):
  """Remove JUMP_BACKWARD instructions which are exception handling for async for.

  These are not used during the regular pytype control flow analysis.
  """
  new_blocks = []
  for block in blocks:
    last_op = block.code[-1]
    if (
        isinstance(last_op, opcodes.JUMP_BACKWARD)
        and isinstance(last_op.target, opcodes.END_SEND)
        and len(block.code) >= 2
        and isinstance(block.code[-2], opcodes.CLEANUP_THROW)
    ):
      continue
    new_blocks.append(block)

  return new_blocks


def compute_order(
    bytecode: list[opcodes.Opcode], python_version
) -> list[Block]:
  """Split bytecode into blocks and order the blocks.

  This builds an "ancestor first" ordering of the basic blocks of the bytecode.

  Args:
    bytecode: A list of instances of opcodes.Opcode. (E.g. returned from
      opcodes.dis())

  Returns:
    A list of Block instances.
  """
  processed_blocks = set()
  blocks = _split_bytecode(bytecode, processed_blocks, python_version)
  if python_version >= (3, 12):
    blocks = _remove_jump_back_block(blocks)
    blocks = _remove_jmp_to_get_anext_and_merge(blocks, processed_blocks)
  first_op_to_block = {block.code[0]: block for block in blocks}
  for i, block in enumerate(blocks):
    next_block = blocks[i + 1] if i < len(blocks) - 1 else None
    if block in processed_blocks:
      continue
    first_op, last_op = block.code[0], block.code[-1]
    if next_block and not last_op.no_next():
      block.connect_outgoing(next_block)
    if first_op.target:
      # Handles SETUP_EXCEPT -> except block
      block.connect_outgoing(first_op_to_block[first_op.target])
    if last_op.target:
      block.connect_outgoing(first_op_to_block[last_op.target])
    if last_op.block_target:
      block.connect_outgoing(first_op_to_block[last_op.block_target])
  return cfg_utils.order_nodes(blocks)


def _order_code(dis_code: pycnite.types.DisassembledCode) -> OrderedCode:
  """Split a CodeType object into ordered blocks.

  This takes a CodeType object (i.e., a piece of compiled Python code) and
  splits it into ordered basic blocks.

  Args:
    dis_code: A pycnite.types.DisassembledCode object.

  Returns:
    An OrderedCode instance.
  """
  ops = opcodes.build_opcodes(dis_code)
  add_pop_block_targets(ops)
  blocks = compute_order(ops, dis_code.python_version)
  return OrderedCode(dis_code.code, ops, blocks)


def _process(
    dis_code: pycnite.types.DisassembledCode, block_graph: BlockGraph
) -> OrderedCode:
  """Recursively convert code -> OrderedCode, while collecting a blockgraph."""
  ordered_code = _order_code(dis_code)
  if dis_code.children:
    # dis_code.children is an ordered list of DisassembledCode for every code
    # object in dis_code.code.co_consts
    children = iter(dis_code.children)
    new_consts = list(dis_code.code.co_consts)
    for i, c in enumerate(new_consts):
      if hasattr(c, "co_consts"):
        # This is a CodeType object (because it has co_consts).
        new_consts[i] = _process(next(children), block_graph)
    ordered_code.consts = tuple(new_consts)
  block_graph.add(ordered_code)
  return ordered_code


def process_code(
    code: pycnite.types.CodeTypeBase,
) -> tuple[OrderedCode, BlockGraph]:
  dis_code = pyc_bytecode.dis_all(code)
  block_graph = BlockGraph()
  ordered = _process(dis_code, block_graph)
  return ordered, block_graph
