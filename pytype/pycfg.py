"""Build a Control Flow Graph (CFG) from CPython bytecode.

A class that builds and provides access to a CFG built from CPython bytecode.

For a basic introduction to CFGs see the wikipedia article:
http://en.wikipedia.org/wiki/Control_flow_graph
"""

import bisect
import dis
import itertools
import logging


from pytype import utils

log = logging.getLogger(__name__)

# The following sets contain instructions with specific branching properties.

# "Returning jumps" jump to a statically unknown location, but then return
# and execute the next instruction.
_RETURNING_JUMPS = frozenset([
    dis.opmap["EXEC_STMT"],
    dis.opmap["IMPORT_NAME"],
    dis.opmap["IMPORT_FROM"],
    dis.opmap["IMPORT_STAR"],
    dis.opmap["CALL_FUNCTION"],
    dis.opmap["CALL_FUNCTION_VAR"],
    dis.opmap["CALL_FUNCTION_KW"],
    dis.opmap["CALL_FUNCTION_VAR_KW"]
    ])

# Untargetted unconditional jumps always jump, but do so to some statically
# unknown location. Examples include, raising exceptions and returning from
# functions: in both cases you are jumping but you cannot statically determine
# to where.
_UNTARGETTED_UNCONDITIONAL_JUMPS = frozenset([
    dis.opmap["BREAK_LOOP"],
    dis.opmap["RETURN_VALUE"],
    dis.opmap["RAISE_VARARGS"],
    ])

# Untargetted conditional jumps may jump to a statically unknown location, but
# may allow control to continue to the next instruction.
_UNTARGETTED_CONDITIONAL_JUMPS = frozenset([
    dis.opmap["END_FINALLY"],  # executes a "why" value (or None) on the stack.
    dis.opmap["WITH_CLEANUP"],
    dis.opmap["YIELD_VALUE"],  # yield is treated as both branching somewhere
                               # unknown and to the next instruction.
    ])

# Targetted unconditional jumps always jump to a statically known target
# instruction.
_TARGETTED_UNCONDITIONAL_JUMPS = frozenset([
    dis.opmap["CONTINUE_LOOP"],
    dis.opmap["JUMP_FORWARD"],
    dis.opmap["JUMP_ABSOLUTE"],
    ])

# Targetted conditional jumps either jump to a statically known target or they
# continue to the next instruction.
_TARGETTED_CONDITIONAL_JUMPS = frozenset([
    dis.opmap["POP_JUMP_IF_TRUE"],
    dis.opmap["POP_JUMP_IF_FALSE"],
    dis.opmap["JUMP_IF_TRUE_OR_POP"],
    dis.opmap["JUMP_IF_FALSE_OR_POP"],
    dis.opmap["FOR_ITER"],
    # TODO(kramm): SETUP_EXCEPT and SETUP_FINALLY do not actually jump, even
    # though they have a jump target. All they do is store their jump target on
    # the block stack. After this, the jump might happen at any time.
    # However, for the purpose of CFG creation, we need to connect an outgoing
    # edge to at least one instruction within the try/except or try/finally
    # code, so we might as well just attach it to the first one.
    dis.opmap["SETUP_EXCEPT"],
    dis.opmap["SETUP_FINALLY"],
    ])

_POP_AND_JUMP_JUMPS = frozenset([
    dis.opmap["POP_JUMP_IF_FALSE"],
    dis.opmap["POP_JUMP_IF_TRUE"],
    ])

_JUMP_AND_POP_JUMPS = frozenset([
    # If FOR_ITER jumps to the end of the loop, it will pop the top stack item,
    # which is typically an iterator.
    dis.opmap["FOR_ITER"],
    ])

# Count both jumps that always pop as well as jumps that only pop if they jump:
_POPPING_JUMPS = _POP_AND_JUMP_JUMPS | _JUMP_AND_POP_JUMPS

_LATE_JUMPS = frozenset([
    dis.opmap["SETUP_EXCEPT"],
    dis.opmap["SETUP_FINALLY"],
    ])


_TARGETTED_JUMPS = (_TARGETTED_CONDITIONAL_JUMPS |
                    _TARGETTED_UNCONDITIONAL_JUMPS)

_CONDITIONAL_JUMPS = (_TARGETTED_CONDITIONAL_JUMPS |
                      _UNTARGETTED_CONDITIONAL_JUMPS)

_UNTARGETTED_JUMPS = (_UNTARGETTED_CONDITIONAL_JUMPS |
                      _UNTARGETTED_UNCONDITIONAL_JUMPS)


def _parse_instructions(code):
  """A generator yielding each instruction in code.

  Args:
    code: A bytecode string (not a code object).

  Yields:
    A triple (opcode, argument or None, offset) for each instruction in code.
    Where offset is the byte offset of the beginning of the instruction.

  This is derived from dis.findlabels in the Python standard library.
  """
  n = len(code)
  i = 0
  while i < n:
    offset = i
    op = ord(code[i])
    i += 1
    oparg = None
    if op >= dis.HAVE_ARGUMENT:
      oparg = ord(code[i]) + ord(code[i+1])*256
      i += 2
    next_offset = offset + (1 if oparg is None else 3)
    yield (op, oparg, offset, next_offset)


class InstructionsIndex(object):
  """An index of all the instructions in a code object.

  Attributes:
    instruction_offsets: A list of instruction offsets.
  """

  def __init__(self, code):
    self.code_length = len(code)
    self.instruction_offsets = [i for _, _, i, _ in _parse_instructions(code)]

  def prev(self, offset):
    """Return the offset of the previous instruction.

    Args:
      offset: The offset of an instruction in the code.

    Returns:
      The offset of the instruction immediately before the instruction specified
      by the offset argument.

    Raises:
      IndexError: If the offset is outside the range of valid instructions.
    """
    if offset < 0:
      raise IndexError("Instruction offset cannot be less than 0")
    if offset > self.instruction_offsets[-1]:
      raise IndexError("Instruction offset cannot be greater than "
                       "the offset of the last instruction")
    # Find the rightmost instruction offset that is less than the offset
    # argument, this will be the previous instruction because it is closest
    # instruction that is before the offset.
    return self.instruction_offsets[
        bisect.bisect_left(self.instruction_offsets, offset) - 1]

  def next(self, offset):
    """Return the offset of the next instruction.

    Args:
      offset: The offset of an instruction in the code.

    Returns:
      The offset of the instruction immediately after the instruction specified
      by the offset argument. If the instruction is the last instruction, None
      is returned.

    Raises:
      IndexError: If the offset is outside the range of valid instructions.
    """
    if offset < 0:
      raise IndexError("Instruction offset cannot be less than 0")
    if offset == self.instruction_offsets[-1]:
      return None
    if offset > self.instruction_offsets[-1]:
      raise IndexError("Instruction offset cannot be greater than "
                       "the offset of the last instruction")
    # Find the leftmost instruction offset that is greater than the offset
    # argument, this will be the next instruction because it is closest
    # instruction that is after the offset.

    pos = bisect.bisect_right(self.instruction_offsets, offset)
    return self.instruction_offsets[pos]


class _UnknownTarget(object):
  """Class of UNKNOWN_TARGET."""

  def get_name(self):
    return "unknown"


# A value to describe unknown targets of jumps, e.g. if we call an function
# but don't know the function at compile time.
UNKNOWN_TARGET = _UnknownTarget()


def _find_jumps(code):
  """Detect all offsets in a byte code which are instructions that can jump.

  Args:
    code: A bytecode string (not a code object).

  Returns:
    A pair of a dict and set. The dict mapping the offsets of jump instructions
    to sets with the same semantics as outgoing in Block. The set of all the
    jump targets it found.
  """
  all_targets = set()
  jumps = {}
  for op, oparg, i, next_i in _parse_instructions(code):
    targets = set()
    if op in _TARGETTED_JUMPS and oparg is not None:
      # Add the known jump target
      targets.add(oparg + (next_i if op in dis.hasjrel else 0))

    if op in _CONDITIONAL_JUMPS:
      # The jump is conditional so add the next instruction as a target
      targets.add(next_i)

    if op in _UNTARGETTED_JUMPS:
      # The jump is untargetted so add an unknown target
      targets.add(UNKNOWN_TARGET)

    if op in _RETURNING_JUMPS:
      targets.add(next_i)
      targets.add(UNKNOWN_TARGET)
      all_targets.add(next_i)

    if op in _LATE_JUMPS:
      # Record this target, but not as a specific jump for this instruction.
      all_targets.add(oparg + (next_i if op in dis.hasjrel else 0))

    if targets:
      jumps[i] = targets
      all_targets.update(t for t in targets if t != UNKNOWN_TARGET)
  return jumps, all_targets


def _find_popping_jumps(code):
  return {arg + (next_i if op in dis.hasjrel else 0)
          for op, arg, _, next_i in _parse_instructions(code)
          if op in _JUMP_AND_POP_JUMPS}  # TODO(kramm): Use _POP_AND_JUMP_JUMPS


def _find_exception_handlers(code):
  assert all(op in dis.hasjrel for op in _LATE_JUMPS)
  return {next_i + arg for op, arg, _, next_i in _parse_instructions(code)
          if op in _LATE_JUMPS}


class Block(object):
  """A Block instance represents a basic block in the CFG.

  Each basic block has at most one jump instruction which is always at the
  end. In this representation we will not add forward jumps to blocks that don't
  have them and instead just take a block that has no jump instruction as
  implicitly jumping to the next instruction when it reaches the end of the
  block. Control may only jump to the beginning of a basic block, so if any
  instruction in a basic block executes they all do and they do so in order.

  Attributes:

    begin, end: The beginning and ending (resp) offsets of the basic block in
                bytes.

    outgoing: A set of blocks that the last instruction of this basic block can
              branch to. It's possible for this list to contain UNKNOWN_TARGET,
              due to exceptions, for instance.

    incoming: A set of blocks that can branch to the beginning of this
              basic block.

    following_block: The block right after this block. Might or might not be in
              outgoing.

    code: The code object that contains this basic block.

    needs_pop: If this block is preceded by a "jump and pop" instruction (e.g.
               FOR_ITER), i.e. whether we need to pop a value of the stack if
               we come from the preceding block.

    needs_exc_push: If this block is an exception handler, it will expect to
                    find the triple (exc_type, val, tb) on the stack.

    id: An integer that uniquely identifies this block within a block_table.
        Used e.g. for deterministic ordering. Currently, this is the same as
        the "begin" attribute and thus, the same for multiple executions of the
        program.

  This object uses the identity hash and equality. This is correct as there
  should never be more than one block object that represents the same actual
  basic block.
  """

  def __init__(self, begin, end, code, block_table, needs_pop, needs_exc_push):
    self.outgoing = set()
    self.incoming = set()
    self.begin = begin
    self.end = end
    self.code = code
    self.block_table = block_table
    self.pop_on_enter = needs_pop
    self.needs_exc_push = needs_exc_push
    self.following_block = None  # filled in by BlockTable
    self.id = begin

  @property
  def jumps(self):
    """Return all other blocks this block jumps to (not: falls through to)."""
    return [b for b in self.outgoing
            if b not in (self.following_block, UNKNOWN_TARGET)]

  def get_name(self):
    return "{}:{}-{}".format(self.block_table.get_filename(),
                             self.block_table.get_line(self.begin),
                             self.block_table.get_line(self.end))

  def __repr__(self):
    return "[{}, {}]".format(self.begin, self.end)


class BlockTable(object):
  """A table of basic blocks in a single bytecode object.

  An UNKNOWN_TARGET in an outgoing list means that that block can branch to an
  unknown location (usually by returning or raising an exception). At the
  moment, continue and break are also treated this way, however it will be
  possible to remove them as the static target is known from the enclosing
  SETUP_LOOP instruction.

  The algorithm to build the Control Flow Graph (CFG) is the naive algorithm
  presented in many compilers classes and probably most compiler text books. We
  simply find all the instructions where CFGs end and begin, make sure they
  match up (there is a begin after every end), and then build a basic block for
  ever range between a beginning and an end. This may not produce the smallest
  possible CFG, but it will produce a correct one because every branch point
  becomes the end of a basic block and every instruction that is branched to
  becomes the beginning of a basic block.
  """

  def __init__(self, code):
    """Construct a table with the blocks in the given code object.

    Args:
      code: a code object (such as function.func_code) to process.
    """
    # TODO(kramm): This constructor is way too long and way too confusing.

    self.code = code
    self.line_offsets, self.lines = zip(*dis.findlinestarts(self.code))

    instruction_index = InstructionsIndex(code.co_code)

    # Get a map from jump instructions to jump targets and a combined set of all
    # targets.
    jumps, all_targets = _find_jumps(code.co_code)

    # Dead code can fall through at the end. E.g. END_FINALLY.
    all_targets.discard(len(code.co_code))
    for _, targets in jumps.items():
      targets.discard(len(code.co_code))

    # TODO(ampere): Using dis.findlabels may not be the right
    # thing. Specifically it is not clear when the targets of SETUP_*
    # instructions should be used to make basic blocks.

    # Make a list of all the directly obvious block begins from the jump targets
    # found above and the labels found by dis.
    direct_begins = all_targets.union(dis.findlabels(code.co_code))

    # New blocks start after jump instructions.
    direct_ends = filter(None, [instruction_index.next(i)
                                for i in jumps.viewkeys()])

    # The actual sorted list of begins is built using the direct_begins along
    # with all instructions that follow a jump instruction. Also the beginning
    # of the code is a begin.
    begins = [0] + sorted(set(list(direct_begins) + list(direct_ends)))
    # The actual ends are every instruction that proceeds a real block begin and
    # the last instruction in the code. Since we included the instruction after
    # every jump above this will include every jump and every instruction that
    # comes before a target.
    ends = ([instruction_index.prev(i) for i in begins if i > 0] +
            [instruction_index.instruction_offsets[-1]])

    # Add targets for the ends of basic blocks that don't have a real jump
    # instruction.
    for end in ends:
      if end not in jumps:
        jumps[end] = set([instruction_index.next(end)])

    # Build a reverse mapping from jump targets to the instructions that jump to
    # them.
    reversemap = {0: set()}
    for (jump, targets) in jumps.items():
      for target in targets:
        reversemap.setdefault(target, set()).add(jump)
    for begin in begins:
      if begin not in reversemap:
        reversemap[begin] = set()

    assert len(begins) == len(ends)

    pop_locations = _find_popping_jumps(code.co_code)
    exception_handlers = _find_exception_handlers(code.co_code)

    # Build the actual basic blocks by pairing the begins and ends directly.
    self._blocks = [
        Block(begin, end, code, self,
              needs_pop=(begin in pop_locations),
              needs_exc_push=(begin in exception_handlers),
             )
        for begin, end in itertools.izip(begins, ends)]

    for b1, b2 in zip(self._blocks, self._blocks[1:]):
      b1.following_block = b2

    # Build a begins list for use with bisect
    self._block_begins = [b.begin for b in self._blocks]
    # Fill in incoming and outgoing
    for block in self._blocks:
      block.outgoing = frozenset(
          self.get_basic_block(o) if o is not UNKNOWN_TARGET else UNKNOWN_TARGET
          for o in jumps[block.end])
      block.incoming = frozenset(
          self.get_basic_block(o)
          for o in reversemap[block.begin])

  def get_basic_block(self, index):
    """Get the basic block that contains the instruction at the given index."""
    return self._blocks[bisect.bisect_right(self._block_begins, index) - 1]

  def get_line(self, index):
    """Get the line number for an instruction.

    Args:
      index: The offset of the instruction.

    Returns:
      The line number of the specified instruction.
    """
    return self.lines[max(bisect.bisect_right(self.line_offsets, index)-1, 0)]

  def get_filename(self):
    """Get the filename of the code object used in this table.

    Returns:
      The string filename.
    """
    return self.code.co_filename

  def get_ancestors_first_traversal(self):
    return utils.order_nodes(self._blocks)

  def get_any_jump_source(self, block):
    for src in self._blocks:
      if block in src.outgoing:
        return src


class CFG(object):
  """A Control Flow Graph object.

  The CFG may contain any number of code objects, but edges never go between
  code objects.
  """

  def __init__(self):
    """Initialize a CFG object."""
    self._block_tables = {}

  def get_block_table(self, code):
    """Get (building if needed) the BlockTable for a given code object."""
    if code in self._block_tables:
      ret = self._block_tables[code]
    else:
      ret = BlockTable(code)
      self._block_tables[code] = ret
    return ret

  def get_basic_block(self, code, index):
    """Get a basic block by code object and index."""
    blocktable = self.get_block_table(code)
    return blocktable.get_basic_block(index)


def _bytecode_repr(code):
  """Generate a python expression that evaluates to the bytecode.

  Args:
    code: A python code string.
  Returns:
    A human readable and python parsable expression that gives the bytecode.
  """
  ret = []
  for op, oparg, i, next_i in _parse_instructions(code):
    sb = "dis.opmap['" + dis.opname[op] + "']"
    if oparg is not None:
      sb += ", {}, {}".format(oparg & 255, (oparg >> 8) & 255)
    sb += ",  # " + str(i)
    if oparg is not None:
      if op in dis.hasjrel:
        assert next_i == i + 3
        sb += ", dest=" + str(next_i + oparg)
      elif op in dis.hasjabs:
        sb += ", dest=" + str(oparg)
      else:
        sb += ", arg=" + str(oparg)
    ret.append(sb)
  return "pycfg._list_to_string([\n  " + ",\n  ".join(ret) + "\n  ])"


def _list_to_string(lst):
  return "".join(chr(c) for c in lst)


def opcode_is_call(code):
  return ord(code) in _RETURNING_JUMPS
