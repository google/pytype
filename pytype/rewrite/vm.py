"""An abstract virtual machine for type analysis of python bytecode."""

from typing import Dict, List

from pytype.blocks import blocks
from pytype.rewrite.flow import variables
from pytype.rewrite.flow import vm_base


class VM(vm_base.VmBase):
  """Virtual machine."""

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
    super().run()
    assert not self._stack
