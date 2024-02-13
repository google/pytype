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
    self._module_frame: frame.Frame = None

  def _run_module(self) -> None:
    assert not self._module_frame
    self._module_frame = frame.Frame(
        name='__main__',
        code=self._code,
        initial_locals=self._initial_globals,
        initial_globals=self._initial_globals,
    )
    self._module_frame.run()

  def _run_function(self, func: abstract.Function) -> frame.Frame:
    assert self._module_frame
    func_frame = frame.Frame(
        name=func.name,
        code=func.code,
        initial_locals={},
        initial_globals=self._module_frame.final_locals,
    )
    func_frame.run()
    return func_frame

  def analyze_all_defs(self):
    self._run_module()
    functions = list(self._module_frame.functions)
    while functions:
      func = functions.pop(0)
      func_frame = self._run_function(func)
      functions.extend(func_frame.functions)

  def infer_stub(self):
    self._run_module()
    for var in self._module_frame.final_locals.values():
      for value in var.values:
        if isinstance(value, abstract.Function):
          self._run_function(value)
