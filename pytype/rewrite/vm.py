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
    self._module_frame = frame.Frame.make_module_frame(
        self._code, self._initial_globals)
    self._module_frame.run()

  def analyze_all_defs(self):
    self._run_module()
    function_frames = [self._module_frame.make_child_frame(f)
                       for f in self._module_frame.functions]
    while function_frames:
      func_frame = function_frames.pop(0)
      func_frame.run()
      function_frames.extend(func_frame.make_child_frame(f)
                             for f in func_frame.functions)

  def infer_stub(self):
    self._run_module()
    for value in self._module_frame.final_locals:
      if isinstance(value, abstract.Function):
        function_frame = self._module_frame.make_child_frame(value)
        function_frame.run()
