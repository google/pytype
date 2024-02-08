"""A frame of an abstract VM for type analysis of python bytecode."""

from typing import Dict, List

from pytype.blocks import blocks
from pytype.rewrite import abstract
from pytype.rewrite.flow import frame_base
from pytype.rewrite.flow import variables


class _DataStack:
  """Data stack."""

  def __init__(self):
    self._stack: List[variables.Variable[abstract.BaseValue]] = []

  def push(self, var: variables.Variable[abstract.BaseValue]) -> None:
    self._stack.append(var)

  def pop(self) -> variables.Variable[abstract.BaseValue]:
    return self._stack.pop()

  def top(self):
    return self._stack[-1]

  def __bool__(self):
    return bool(self._stack)

  def __len__(self):
    return len(self._stack)


class Frame(frame_base.FrameBase[abstract.BaseValue]):
  """Virtual machine frame."""

  def __init__(
      self,
      code: blocks.OrderedCode,
      initial_locals: Dict[str, variables.Variable[abstract.BaseValue]],
      globals_: Dict[str, variables.Variable[abstract.BaseValue]],
  ):
    super().__init__(code, initial_locals)
    self._globals = globals_  # globally scoped names
    self._stack = _DataStack()  # data stack

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
    constant = abstract.PythonConstant(self._code.consts[opcode.arg])
    self._stack.push(variables.Variable.from_value(constant))

  def byte_RETURN_VALUE(self, opcode):
    unused_return_value = self._stack.pop()

  def byte_STORE_NAME(self, opcode):
    name = opcode.argval
    value = self._stack.pop()
    self._current_state.store_local(name, value)
