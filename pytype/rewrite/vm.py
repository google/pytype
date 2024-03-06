"""An abstract virtual machine for type analysis of python bytecode."""

from typing import Dict

from pytype import config
from pytype.blocks import blocks
from pytype.pyc import pyc
from pytype.rewrite import convert
from pytype.rewrite import frame as frame_lib
from pytype.rewrite.abstract import abstract
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
    self._module_frame: frame_lib.Frame = None

  @classmethod
  def from_source(cls, src: str, options: config.Options) -> 'VirtualMachine':
    code = _get_bytecode(src, options)
    initial_globals = convert.get_module_globals(options.python_version)
    return cls(code, initial_globals)

  def _run_module(self) -> None:
    assert not self._module_frame
    self._module_frame = frame_lib.Frame.make_module_frame(
        self._code, self._initial_globals)
    self._module_frame.run()

  def analyze_all_defs(self):
    """Analyzes all class and function definitions."""
    self._run_module()
    function_frames = []

    def queue(frame):
      for f in frame.functions:
        for sig in f.signatures:
          function_frames.append(
              frame.make_child_frame(f, sig.make_fake_args()))

    queue(self._module_frame)
    while function_frames:
      func_frame = function_frames.pop(0)
      func_frame.run()
      queue(func_frame)

  def infer_stub(self):
    self._run_module()
    for value in self._module_frame.final_locals:
      if isinstance(value, abstract.InterpreterFunction):
        for sig in value.signatures:
          function_frame = self._module_frame.make_child_frame(
              value, sig.make_fake_args())
          function_frame.run()


def _get_bytecode(src: str, options: config.Options) -> blocks.OrderedCode:
  code = pyc.compile_src(
      src=src,
      python_version=options.python_version,
      python_exe=options.python_exe,
      filename=options.input,
      mode='exec',
  )
  ordered_code, unused_block_graph = blocks.process_code(code)
  return ordered_code
