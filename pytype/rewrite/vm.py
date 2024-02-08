"""An abstract virtual machine for type analysis of python bytecode."""

from typing import Dict

from pytype.blocks import blocks
from pytype.rewrite import abstract
from pytype.rewrite import frame
from pytype.rewrite.flow import variables


class VirtualMachine:
  """Virtual machine."""

  def __init__(
      self,
      code: blocks.OrderedCode,
      initial_globals: Dict[str, variables.Variable[abstract.BaseValue]],
  ):
    self._code = code
    self._initial_globals = initial_globals

  def _run(self):
    module_frame = frame.Frame(
        name='__main__',
        code=self._code,
        initial_locals=self._initial_globals,
        initial_globals=self._initial_globals,
    )
    module_frame.run()
    return module_frame

  def analyze_all_defs(self):
    module_frame = self._run()
    for func in module_frame.functions:
      del func
      raise NotImplementedError('Function analysis not implemented yet')

  def infer_stub(self):
    module_frame = self._run()
    for name, var in module_frame.final_locals:
      del name, var
      raise NotImplementedError('Pytd generation not implemented yet')
