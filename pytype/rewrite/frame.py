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
_FrameFunction = abstract.InterpreterFunction['Frame']


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
    self._functions: List[_FrameFunction] = []
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
  def functions(self) -> Sequence[_FrameFunction]:
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
    self._finalize_locals()

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
      func: _FrameFunction,
      initial_locals: Mapping[str, _AbstractVariable],
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

  def get_return_value(self) -> abstract.BaseValue:
    # TODO(b/241479600): Return union of values from byte_RETURN_VALUE ops.
    return abstract.PythonConstant(None)

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
      args: abstract.Args,
  ) -> None:
    ret_values = []
    for func in func_var.values:
      if isinstance(func, (abstract.InterpreterFunction,
                           abstract.InterpreterClass,
                           abstract.BoundFunction)):
        frame = func.call(args)
        ret_values.append(frame.get_return_value())
      elif func is abstract.BUILD_CLASS:
        class_body, name = args.posargs
        builder = class_body.get_atomic_value(_FrameFunction)
        frame = builder.call(abstract.Args())
        cls = abstract.InterpreterClass(
            name=abstract.get_atomic_constant(name, str),
            members=dict(frame.final_locals),
            functions=frame.functions,
            classes=frame.classes,
        )
        self._classes.append(cls)
        ret_values.append(cls)
      else:
        raise NotImplementedError('CALL not fully implemented')
    self._stack.push(
        variables.Variable(tuple(variables.Binding(v) for v in ret_values)))

  def _finalize_locals(self) -> None:
    final_values = {}
    for name, var in self._final_locals.items():
      values = var.values
      if len(values) > 1:
        raise NotImplementedError('Multiple bindings not yet supported')
      elif values:
        final_values[name] = values[0]
      else:
        raise NotImplementedError('Empty variable not yet supported')
    # We've stored SET_ATTR results as local values. Now actually perform the
    # attribute setting.
    # TODO(b/241479600): If we're deep in a stack of method calls, we should
    # instead merge the attribute values into the parent frame so that any
    # conditions on the bindings are preserved.
    for name, value in final_values.items():
      target_name, dot, attr_name = name.rpartition('.')
      if not dot or target_name not in self._final_locals:
        continue
      for target in self._final_locals[target_name].values:
        target.set_attribute(attr_name, value)
    self.final_locals = immutabledict.immutabledict(final_values)

  def _load_attr(
      self, target_var: _AbstractVariable, attr_name: str) -> _AbstractVariable:
    if target_var.name:
      name = f'{target_var.name}.{attr_name}'
    else:
      name = None
    try:
      # Check if we've stored the attribute in the current frame.
      return self.load_local(name)
    except KeyError as e:
      # We're loading an attribute without a locally stored value.
      attr_bindings = []
      for target in target_var.values:
        attr = target.get_attribute(attr_name)
        if not attr:
          raise NotImplementedError('Attribute error') from e
        # TODO(b/241479600): If there's a condition on the target binding, we
        # should copy it.
        attr_bindings.append(variables.Binding(attr))
      return variables.Variable(tuple(attr_bindings), name)

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

  def byte_STORE_ATTR(self, opcode):
    attr_name = opcode.argval
    attr, target = self._stack.popn(2)
    if not target.name:
      raise NotImplementedError('Missing target name')
    full_name = f'{target.name}.{attr_name}'
    self.store_local(full_name, attr)

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
    func = abstract.InterpreterFunction(name, code, enclosing_scope, self)
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

  def byte_LOAD_ATTR(self, opcode):
    attr_name = opcode.argval
    target_var = self._stack.pop()
    self._stack.push(self._load_attr(target_var, attr_name))

  def byte_LOAD_METHOD(self, opcode):
    method_name = opcode.argval
    instance_var = self._stack.pop()
    # https://docs.python.org/3/library/dis.html#opcode-LOAD_METHOD says that
    # this opcode should push two values onto the stack: either the unbound
    # method and its `self` or NULL and the bound method. Since we always
    # retrieve a bound method, we push the NULL
    self._stack.push(abstract.NULL.to_variable())
    self._stack.push(self._load_attr(instance_var, method_name))

  def byte_PRECALL(self, opcode):
    del opcode  # unused

  def byte_CALL(self, opcode):
    sentinel, *rest = self._stack.popn(opcode.arg + 2)
    if not sentinel.has_atomic_value(abstract.NULL):
      raise NotImplementedError('CALL not fully implemented')
    func_var, *args = rest
    self._call_function(func_var, abstract.Args(posargs=args))

  def byte_CALL_FUNCTION(self, opcode):
    args = self._stack.popn(opcode.arg)
    func_var = self._stack.pop()
    self._call_function(func_var, abstract.Args(posargs=args))

  def byte_CALL_METHOD(self, opcode):
    args = self._stack.popn(opcode.arg)
    func_var = self._stack.pop()
    # pop the NULL off the stack (see LOAD_METHOD)
    self._stack.pop_and_discard()
    self._call_function(func_var, abstract.Args(posargs=args))

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
