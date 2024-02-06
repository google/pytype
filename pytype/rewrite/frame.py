"""A frame of an abstract VM for type analysis of python bytecode."""

from typing import Dict, List

from pytype.blocks import blocks
from pytype.rewrite.flow import frame_base
from pytype.rewrite.flow import variables


class Frame(frame_base.FrameBase):
  """Virtual machine frame."""

  def __init__(
      self,
      code: blocks.OrderedCode,
      initial_locals: Dict[str, variables.Variable],
      globals_: Dict[str, variables.Variable],
  ):
    super().__init__(code, initial_locals)
    self._globals = globals_  # globally scoped names
    self._stack: List[variables.Variable] = []  # data stack

  def run(self) -> None:
    assert not self._stack
    while True:
      try:
        self.step()
      except frame_base.FrameConsumedError:
        break
    assert not self._stack

  def byte_RESUME(self, opcode):
    del opcode  # unused

  def byte_LOAD_CONST(self, opcode):
    constant = opcode.argval
    # TODO(b/241479600): Wrap this in an abstract value.
    self._stack.append(variables.Variable.from_value(constant))

  def byte_RETURN_VALUE(self, opcode):
    unused_return_value = self._stack.pop()
