"""A frame of an abstract VM for type analysis of python bytecode."""

from typing import Dict, List, Optional, Sequence, Set

from pytype.blocks import blocks
from pytype.rewrite import abstract
from pytype.rewrite import stack
from pytype.rewrite.flow import frame_base
from pytype.rewrite.flow import variables

_AbstractVariable = variables.Variable[abstract.BaseValue]  # typing alias


class Frame(frame_base.FrameBase[abstract.BaseValue]):
  """Virtual machine frame."""

  def __init__(
      self,
      name: str,
      code: blocks.OrderedCode,
      initial_locals: Dict[str, _AbstractVariable],
      initial_globals: Dict[str, _AbstractVariable],
      f_back: Optional['Frame'] = None,
  ):
    super().__init__(code, initial_locals)
    self.name = name  # name of the frame
    self._initial_globals = initial_globals  # global names before frame runs
    self._f_back = f_back  # the frame that created this one, if any
    self._stack = stack.DataStack()  # data stack
    # Names of globals shadowed in the current frame
    self._shadowed_globals: Set[str] = set()
    # All functions created during execution
    self._functions: List[abstract.Function] = []

  @property
  def functions(self) -> Sequence[abstract.Function]:
    return tuple(self._functions)

  @property
  def _is_module_frame(self) -> bool:
    return self.name == '__main__'

  def run(self) -> None:
    assert not self._stack
    while True:
      try:
        self.step()
      except frame_base.FrameConsumedError:
        break
    assert not self._stack
    if self._f_back:
      self._merge_nonlocals_into(self._f_back)

  def store_local(self, name: str, var: _AbstractVariable) -> None:
    self._current_state.store_local(name, var)

  def store_global(self, name: str, var: _AbstractVariable) -> None:
    # We allow modifying globals only when executing the module frame.
    # Otherwise, we shadow the global in current frame. Either way, the behavior
    # is equivalent to storing the global as a local.
    self._current_state.store_local(name, var)
    self._shadowed_globals.add(name)

  def load_local(self, name):
    if not self._is_module_frame and name in self._shadowed_globals:
      raise KeyError(name)
    return self._current_state.load_local(name)

  def load_global(self, name):
    if self._is_module_frame or name in self._shadowed_globals:
      return self._current_state.load_local(name)
    else:
      return self._initial_globals[name].with_name(name)

  def _make_child_frame(self, func: abstract.Function) -> 'Frame':
    current_locals = self._current_state.get_locals()
    if self._is_module_frame:
      # The module frame's locals are the most up-to-date globals.
      initial_globals = current_locals
    else:
      initial_globals = dict(self._initial_globals)
      for name in self._shadowed_globals:
        initial_globals[name] = current_locals[name]
    return Frame(
        name=func.name,
        code=func.code,
        initial_locals={},
        initial_globals=initial_globals,
        f_back=self,
    )

  def _merge_nonlocals_into(self, frame: 'Frame') -> None:
    for name in self._shadowed_globals:
      var = self.final_locals[name]
      frame.store_global(name, var)

  def _call_function(self, func_var: _AbstractVariable) -> None:
    for func in func_var.values:
      if not isinstance(func, abstract.Function):
        raise NotImplementedError('CALL not fully implemented')
      frame = self._make_child_frame(func)
      frame.run()
    dummy_ret = variables.Variable.from_value(abstract.PythonConstant(None))
    self._stack.push(dummy_ret)

  def byte_RESUME(self, opcode):
    del opcode  # unused

  def byte_LOAD_CONST(self, opcode):
    constant = abstract.PythonConstant(self._code.consts[opcode.arg])
    self._stack.push(variables.Variable.from_value(constant))

  def byte_RETURN_VALUE(self, opcode):
    unused_return_value = self._stack.pop()

  def byte_STORE_NAME(self, opcode):
    self.store_local(opcode.argval, self._stack.pop())

  def byte_STORE_FAST(self, opcode):
    self.store_local(opcode.argval, self._stack.pop())

  def byte_STORE_GLOBAL(self, opcode):
    self.store_global(opcode.argval, self._stack.pop())

  def byte_MAKE_FUNCTION(self, opcode):
    if opcode.arg:
      raise NotImplementedError('MAKE_FUNCTION not fully implemented')
    if self._code.python_version >= (3, 11):
      code = self._stack.pop().get_atomic_value().constant
      name = code.qualname
    else:
      name = self._stack.pop().get_atomic_value().constant
      code = self._stack.pop().get_atomic_value().constant
    func = abstract.Function(name, code)
    self._functions.append(func)
    self._stack.push(variables.Variable.from_value(func))

  def byte_PUSH_NULL(self, opcode):
    del opcode  # unused
    self._stack.push(variables.Variable.from_value(abstract.NULL))

  def byte_LOAD_NAME(self, opcode):
    name = opcode.argval
    try:
      var = self.load_local(name)
    except KeyError:
      var = self.load_global(name)
    self._stack.push(var)

  def byte_LOAD_FAST(self, opcode):
    name = opcode.argval
    self._stack.push(self.load_local(name))

  def byte_LOAD_GLOBAL(self, opcode):
    name = opcode.argval
    self._stack.push(self.load_global(name))

  def byte_PRECALL(self, opcode):
    del opcode  # unused

  def byte_CALL(self, opcode):
    if opcode.arg:
      raise NotImplementedError('CALL not fully implemented')
    sentinel, *rest = self._stack.popn(opcode.arg + 2)
    if sentinel.values != (abstract.NULL,):
      raise NotImplementedError('CALL not fully implemented')
    func_var, *unused_args = rest
    self._call_function(func_var)

  def byte_CALL_FUNCTION(self, opcode):
    if opcode.arg:
      raise NotImplementedError('CALL_FUNCTION not fully implemented')
    func_var = self._stack.pop()
    self._call_function(func_var)

  def byte_POP_TOP(self, opcode):
    del opcode  # unused
    self._stack.pop_and_discard()
