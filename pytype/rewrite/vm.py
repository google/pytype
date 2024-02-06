"""An abstract virtual machine for type analysis of python bytecode."""

from typing import Dict, Optional

from pytype.blocks import blocks
from pytype.rewrite import frame
from pytype.rewrite.flow import variables


class VmConsumedError(Exception):
  """Raised when the VM has already been run."""


class VirtualMachine:
  """Virtual machine."""

  def __init__(
      self,
      code: blocks.OrderedCode,
      globals_: Dict[str, variables.Variable],
  ):
    self._code = code
    self._globals = globals_
    self._module_frame: Optional[frame.Frame] = None

  def run(self):
    if self._module_frame:
      raise VmConsumedError()
    self._module_frame = frame.Frame(
        self._code, initial_locals=self._globals, globals_=self._globals)
    self._module_frame.run()
