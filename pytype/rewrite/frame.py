"""A frame of an abstract VM for type analysis of python bytecode."""

import enum
import logging
from typing import FrozenSet, List, Mapping, Optional, Sequence, Set

import immutabledict
from pycnite import marshal as pyc_marshal
from pytype.blocks import blocks
from pytype.rewrite import stack
from pytype.rewrite.abstract import abstract
from pytype.rewrite.flow import frame_base
from pytype.rewrite.flow import variables

log = logging.getLogger(__name__)

_EMPTY_MAP = immutabledict.immutabledict()

# Type aliases
_AbstractVariable = variables.Variable[abstract.BaseValue]
_VarMap = Mapping[str, _AbstractVariable]


class _Scope(enum.Enum):
  ENCLOSING = enum.auto()
  GLOBAL = enum.auto()


class _ShadowedNonlocals:
  """Tracks shadowed nonlocal names."""

  def __init__(self):
    self._enclosing: Set[str] = set()
    self._globals: Set[str] = set()

  def add_enclosing(self, name: str) -> None:
    self._enclosing.add(name)

  def add_global(self, name: str) -> None:
    self._globals.add(name)

  def has_scope(self, name: str, scope: _Scope) -> bool:
    if scope is _Scope.ENCLOSING:
      return name in self._enclosing
    elif scope is _Scope.GLOBAL:
      return name in self._globals
    else:
      raise ValueError(f'Unrecognized scope: {scope}')

  def get_names(self, scope: _Scope) -> FrozenSet[str]:
    if scope is _Scope.ENCLOSING:
      return frozenset(self._enclosing)
    elif scope is _Scope.GLOBAL:
      return frozenset(self._globals)
    else:
      raise NotImplementedError(f'Unrecognized scope: {scope}')


class Frame(frame_base.FrameBase[abstract.BaseValue]):
  """Virtual machine frame.

  Attributes:
    name: The name of the frame.
    final_locals: The final `locals` dictionary after the frame finishes
      executing, with Variables flattened to BaseValues.
  """

  def __init__(
      self,
      name: str,
      code: blocks.OrderedCode,
      *,
      initial_locals: _VarMap = _EMPTY_MAP,
      initial_enclosing: _VarMap = _EMPTY_MAP,
      initial_globals: _VarMap = _EMPTY_MAP,
      f_back: Optional['Frame'] = None,
  ):
    super().__init__(code, initial_locals)
    self.name = name  # name of the frame

    # Sanity checks: a module frame should have the same locals and globals. A
    # frame should have an enclosing scope only if it has a parent (f_back).
    assert not self._is_module_frame or initial_locals == initial_globals
    assert f_back or not initial_enclosing

    # Initial variables in enclosing and global scopes
    self._initial_enclosing = initial_enclosing
    self._initial_globals = initial_globals
    self._f_back = f_back  # the frame that created this one, if any
    self._stack = stack.DataStack()  # data stack
    # Names of nonlocals shadowed in the current frame
    self._shadowed_nonlocals = _ShadowedNonlocals()
    # All functions and classes created during execution
    self._functions: List[abstract.InterpreterFunction] = []
    self._classes: List[abstract.InterpreterClass] = []
    # Final values of locals, unwrapped from variables
    self.final_locals: Mapping[str, abstract.BaseValue] = None

  def __repr__(self):
    return f'Frame({self.name})'

  @classmethod
  def make_module_frame(
      cls,
      code: blocks.OrderedCode,
      initial_globals: _VarMap,
  ) -> 'Frame':
    return cls(
        name='__main__',
        code=code,
        initial_locals=initial_globals,
        initial_enclosing={},
        initial_globals=initial_globals,
        f_back=None,
    )

  @property
  def functions(self) -> Sequence[abstract.InterpreterFunction]:
    return tuple(self._functions)

  @property
  def classes(self) -> Sequence[abstract.InterpreterClass]:
    return tuple(self._classes)

  @property
  def _is_module_frame(self) -> bool:
    return self.name == '__main__'

  def run(self) -> None:
    log.info('Running frame: %s', self.name)
    assert not self._stack
    while True:
      try:
        self.step()
      except frame_base.FrameConsumedError:
        break
    assert not self._stack
    log.info('Finished running frame: %s', self.name)
    if self._f_back and self._f_back.final_locals is None:
      log.info('Resuming frame: %s', self._f_back.name)
      self._merge_nonlocals_into(self._f_back)
    # Set the current state to None so that the load_* and store_* methods
    # cannot be used to modify finalized locals.
    self._current_state = None
    self.final_locals = self._final_locals_as_values()

  def store_local(self, name: str, var: _AbstractVariable) -> None:
    self._current_state.store_local(name, var)

  def store_enclosing(self, name: str, var: _AbstractVariable) -> None:
    # We shadow the name from the enclosing scope. We will merge it into f_back
    # when the current frame finishes.
    self._current_state.store_local(name, var)
    self._shadowed_nonlocals.add_enclosing(name)

  def store_global(self, name: str, var: _AbstractVariable) -> None:
    # We allow modifying globals only when executing the module frame.
    # Otherwise, we shadow the global in current frame. Either way, the behavior
    # is equivalent to storing the global as a local.
    self._current_state.store_local(name, var)
    self._shadowed_nonlocals.add_global(name)

  def store_deref(self, name: str, var: _AbstractVariable) -> None:
    # When a name from a parent frame is referenced in a child frame, we make a
    # conceptual distinction between the parent's local scope and the child's
    # enclosing scope. However, at runtime, writing to both is the same
    # operation (STORE_DEREF), so it's convenient to have a store method that
    # emulates this.
    if name in self._initial_enclosing:
      self.store_enclosing(name, var)
    else:
      self.store_local(name, var)

  def load_local(self, name) -> _AbstractVariable:
    if (self._shadowed_nonlocals.has_scope(name, _Scope.ENCLOSING) or
        (not self._is_module_frame and
         self._shadowed_nonlocals.has_scope(name, _Scope.GLOBAL))):
      raise KeyError(name)
    return self._current_state.load_local(name)

  def load_enclosing(self, name) -> _AbstractVariable:
    if self._shadowed_nonlocals.has_scope(name, _Scope.ENCLOSING):
      return self._current_state.load_local(name)
    return self._initial_enclosing[name].with_name(name)

  def load_global(self, name) -> _AbstractVariable:
    if (self._is_module_frame or
        self._shadowed_nonlocals.has_scope(name, _Scope.GLOBAL)):
      return self._current_state.load_local(name)
    return self._initial_globals[name].with_name(name)

  def load_deref(self, name) -> _AbstractVariable:
    # When a name from a parent frame is referenced in a child frame, we make a
    # conceptual distinction between the parent's local scope and the child's
    # enclosing scope. However, at runtime, reading from both is the same
    # operation (LOAD_DEREF), so it's convenient to have a load method that
    # emulates this.
    try:
      return self.load_local(name)
    except KeyError:
      return self.load_enclosing(name)

  def make_child_frame(
      self,
      func: abstract.InterpreterFunction,
      initial_locals: Mapping[str, _AbstractVariable] = _EMPTY_MAP,
  ) -> 'Frame':
    if self._final_locals:
      current_locals = {
          name: val.to_variable() for name, val in self.final_locals.items()}
    else:
      current_locals = self._current_state.get_locals()
    initial_enclosing = {}
    for name in func.enclosing_scope:
      if name in current_locals:
        assert not self._shadowed_nonlocals.has_scope(name, _Scope.GLOBAL)
        initial_enclosing[name] = current_locals[name]
      else:
        initial_enclosing[name] = self._initial_enclosing[name]
    if self._is_module_frame:
      # The module frame's locals are the most up-to-date globals.
      initial_globals = current_locals
    else:
      initial_globals = dict(self._initial_globals)
      for name in self._shadowed_nonlocals.get_names(_Scope.GLOBAL):
        initial_globals[name] = current_locals[name]
    return Frame(
        name=func.name,
        code=func.code,
        initial_locals=initial_locals,
        initial_enclosing=initial_enclosing,
        initial_globals=initial_globals,
        f_back=self,
    )

  def _merge_nonlocals_into(self, frame: 'Frame') -> None:
    for name in self._shadowed_nonlocals.get_names(_Scope.ENCLOSING):
      var = self._final_locals[name]
      frame.store_deref(name, var)
    for name in self._shadowed_nonlocals.get_names(_Scope.GLOBAL):
      var = self._final_locals[name]
      frame.store_global(name, var)

  def _call_function(
      self,
      func_var: _AbstractVariable,
      args: Sequence[_AbstractVariable],
  ) -> None:
    ret_values = []
    for func in func_var.values:
      if isinstance(func, abstract.InterpreterFunction):
        mapped_args = func.map_args(args)
        frame = self.make_child_frame(func, mapped_args)
        frame.run()
        dummy_ret = abstract.PythonConstant(None)
        ret_values.append(dummy_ret)
      elif func is abstract.BUILD_CLASS:
        class_body, name = args
        frame = self.make_child_frame(
            class_body.get_atomic_value(abstract.InterpreterFunction))
        frame.run()
        cls = self._make_class(abstract.get_atomic_constant(name, str), frame)
        self._classes.append(cls)
        ret_values.append(cls)
      else:
        raise NotImplementedError('CALL not fully implemented')
    self._stack.push(
        variables.Variable(tuple(variables.Binding(v) for v in ret_values)))

  def _make_class(self, name: str, class_body: 'Frame'):
    cls = abstract.InterpreterClass(
        name=name,
        members=class_body.final_locals,
        functions=class_body.functions,
        classes=class_body.classes,
    )
    for setup_method_name in cls.setup_methods:
      # TODO(b/324475548): Get and call this method.
      del setup_method_name  # pylint: disable=modified-iterating-list
    return cls

  def _final_locals_as_values(self) -> Mapping[str, abstract.BaseValue]:
    final_values = {}
    for name, var in self._final_locals.items():
      values = var.values
      if len(values) > 1:
        raise NotImplementedError('Multiple bindings not yet supported')
      elif values:
        final_values[name] = values[0]
      else:
        raise NotImplementedError('Empty variable not yet supported')
    return immutabledict.immutabledict(final_values)

  def byte_RESUME(self, opcode):
    del opcode  # unused

  def byte_LOAD_CONST(self, opcode):
    constant = abstract.PythonConstant(self._code.consts[opcode.arg])
    self._stack.push(constant.to_variable())

  def byte_RETURN_VALUE(self, opcode):
    unused_return_value = self._stack.pop()

  def byte_STORE_NAME(self, opcode):
    self.store_local(opcode.argval, self._stack.pop())

  def byte_STORE_FAST(self, opcode):
    self.store_local(opcode.argval, self._stack.pop())

  def byte_STORE_GLOBAL(self, opcode):
    self.store_global(opcode.argval, self._stack.pop())

  def byte_STORE_DEREF(self, opcode):
    self.store_deref(opcode.argval, self._stack.pop())

  def byte_MAKE_FUNCTION(self, opcode):
    if opcode.arg not in (0, pyc_marshal.Flags.MAKE_FUNCTION_HAS_FREE_VARS):
      raise NotImplementedError('MAKE_FUNCTION not fully implemented')
    if self._code.python_version >= (3, 11):
      code = abstract.get_atomic_constant(self._stack.pop(), blocks.OrderedCode)
      name = code.qualname
    else:
      name = abstract.get_atomic_constant(self._stack.pop(), str)
      code = abstract.get_atomic_constant(self._stack.pop(), blocks.OrderedCode)
    if opcode.arg & pyc_marshal.Flags.MAKE_FUNCTION_HAS_FREE_VARS:
      freevars = abstract.get_atomic_constant(self._stack.pop())
      enclosing_scope = tuple(freevar.name for freevar in freevars)
      assert all(enclosing_scope)
    else:
      enclosing_scope = ()
    func = abstract.InterpreterFunction(name, code, enclosing_scope)
    if not (self._stack and
            self._stack.top().has_atomic_value(abstract.BUILD_CLASS)):
      # BUILD_CLASS makes and immediately calls a function that creates the
      # class body; we don't need to store this function for later analysis.
      self._functions.append(func)
    self._stack.push(func.to_variable())

  def byte_PUSH_NULL(self, opcode):
    del opcode  # unused
    self._stack.push(abstract.NULL.to_variable())

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

  def byte_LOAD_DEREF(self, opcode):
    name = opcode.argval
    self._stack.push(self.load_deref(name))

  def byte_LOAD_CLOSURE(self, opcode):
    name = opcode.argval
    self._stack.push(self.load_deref(name))

  def byte_LOAD_GLOBAL(self, opcode):
    name = opcode.argval
    self._stack.push(self.load_global(name))

  def byte_PRECALL(self, opcode):
    del opcode  # unused

  def byte_CALL(self, opcode):
    sentinel, *rest = self._stack.popn(opcode.arg + 2)
    if not sentinel.has_atomic_value(abstract.NULL):
      raise NotImplementedError('CALL not fully implemented')
    func_var, *args = rest
    self._call_function(func_var, args)

  def byte_CALL_FUNCTION(self, opcode):
    args = self._stack.popn(opcode.arg)
    func_var = self._stack.pop()
    self._call_function(func_var, args)

  def byte_POP_TOP(self, opcode):
    del opcode  # unused
    self._stack.pop_and_discard()

  # Pytype tracks variables in enclosing scopes by name rather than emulating
  # the runtime's approach with cells and freevars, so we can ignore the opcodes
  # that deal with the latter.
  def byte_MAKE_CELL(self, opcode):
    del opcode  # unused

  def byte_COPY_FREE_VARS(self, opcode):
    del opcode  # unused

  def byte_BUILD_TUPLE(self, opcode):
    count = opcode.arg
    elements = self._stack.popn(count)
    self._stack.push(abstract.PythonConstant(tuple(elements)).to_variable())

  def byte_LOAD_BUILD_CLASS(self, opcode):
    self._stack.push(abstract.BUILD_CLASS.to_variable())
