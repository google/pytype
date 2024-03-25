"""An abstract virtual machine for type analysis of python bytecode."""

from typing import Dict, Optional, Sequence, Tuple

from pytype import config
from pytype.blocks import blocks
from pytype.errors import errors
from pytype.pyc import pyc
from pytype.pytd import pytd
from pytype.pytd import pytd_utils
from pytype.rewrite import convert
from pytype.rewrite import frame as frame_lib
from pytype.rewrite import output
from pytype.rewrite import pretty_printer
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
    self._errorlog = errors.ErrorLog(pretty_printer.PrettyPrinter())

  @classmethod
  def from_source(
      cls, src: str, options: Optional[config.Options] = None
  ) -> 'VirtualMachine':
    options = options or config.Options.create()
    code = _get_bytecode(src, options)
    initial_globals = convert.get_module_globals(options.python_version)
    return cls(code, initial_globals)

  def _run_module(self) -> None:
    assert not self._module_frame
    self._module_frame = frame_lib.Frame.make_module_frame(
        self._code, self._initial_globals)
    self._module_frame.run()

  def analyze_all_defs(self) -> errors.ErrorLog:
    """Analyzes all class and function definitions."""
    self._run_module()
    parent_frames = [self._module_frame]
    while parent_frames:
      parent_frame = parent_frames.pop(0)
      for f in parent_frame.functions:
        parent_frames.extend(f.analyze())
      classes = _collect_classes(parent_frame)
      for cls in classes:
        instance = cls.instantiate()
        for f in cls.functions:
          parent_frames.extend(f.bind_to(instance).analyze())
    return self._errorlog

  def infer_stub(self) -> Tuple[errors.ErrorLog, pytd.TypeDeclUnit]:
    self._run_module()
    pytd_nodes = []
    for name, value in self._module_frame.final_locals.items():
      if name in output.IGNORED_MODULE_ATTRIBUTES:
        continue
      try:
        pytd_node = output.to_pytd_def(value)
      except NotImplementedError:
        pytd_node = pytd.Constant(name, output.to_pytd_type(value))
      pytd_nodes.append(pytd_node)
    return self._errorlog, pytd_utils.WrapTypeDeclUnit('inferred', pytd_nodes)


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


def _collect_classes(
    frame: frame_lib.Frame) -> Sequence[abstract.InterpreterClass]:
  all_classes = []
  new_classes = list(frame.classes)
  while new_classes:
    cls = new_classes.pop(0)
    all_classes.append(cls)
    new_classes.extend(cls.classes)
  return all_classes
