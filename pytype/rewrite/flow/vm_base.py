"""Base implementation of an abstract virtual machine for bytecode.

This module contains a VmBase class, which provides a base implementation of a
VM that analyzes bytecode one instruction (i.e., opcode) at a time, tracking
variables and conditions. Use VmBase by subclassing it and adding a
byte_{opcode_name} method implementing each opcode.
"""

import dataclasses
from typing import Dict, Optional

from pytype.blocks import blocks
from pytype.rewrite.flow import variables


@dataclasses.dataclass
class BlockState:
  """State of a bytecode block."""

  locals_: Dict[str, variables.Variable]
  condition: variables.Condition = variables.TRUE

  def merge_into(self, other: Optional['BlockState']) -> 'BlockState':
    """Merges 'self' into 'other'."""
    if not other:
      return BlockState(locals_=dict(self.locals_), condition=self.condition)
    if self.locals_ or self.condition is not variables.TRUE:
      raise NotImplementedError(
          'Merging of locals and conditions not implemented yet')
    return other


class VmBase:
  """Virtual machine."""

  def __init__(
      self, code: blocks.OrderedCode,
      initial_locals: Dict[str, variables.Variable],
  ):
    self._code = code  # bytecode
    self._initial_locals = initial_locals  # locally scoped names before VM runs
    self._states: Dict[int, BlockState] = {}  # block id to state
    self._current_state: BlockState = None  # state of the current block

  def run(self) -> None:
    """Runs self._code."""
    # Initialize the state of the first block.
    self._states[self._code.order[0].id] = BlockState(
        locals_=dict(self._initial_locals))
    for block in self._code.order:
      # Grab the block's initial state.
      self._current_state = self._states[block.id]
      # Run the block's opcodes.
      prev_opcode = None
      for opcode in block:
        opname = opcode.__class__.__name__
        try:
          op_impl = getattr(self, f'byte_{opname}')
        except AttributeError as e:
          raise NotImplementedError(f'Opcode {opname} not implemented') from e
        op_impl(opcode)
        prev_opcode = opcode
      # Merge the current state into the next.
      if (prev_opcode and prev_opcode.carry_on_to_next() and
          not prev_opcode.has_known_jump()):
        self._merge_state_into(self._current_state, prev_opcode.next.index)
    self._current_state = None

  def _merge_state_into(self, state: BlockState, block_id: int) -> None:
    self._states[block_id] = state.merge_into(self._states.get(block_id))
