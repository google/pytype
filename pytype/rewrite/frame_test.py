import sys
from typing import Mapping, Type, TypeVar, cast, get_origin

from pytype.pyc import opcodes
from pytype.rewrite import frame as frame_lib
from pytype.rewrite.abstract import abstract
from pytype.rewrite.tests import test_utils
from typing_extensions import assert_type

import unittest

_FrameFunction = abstract.InterpreterFunction[frame_lib.Frame]
_T = TypeVar('_T')


def _get(frame: frame_lib.Frame, name: str, typ: Type[_T]) -> _T:
  val = cast(_T, frame.final_locals[name])
  assert isinstance(val, get_origin(typ) or typ)
  return val


class FrameTestBase(test_utils.ContextfulTestBase):

  def _make_frame(self, src: str, name: str = '__main__') -> frame_lib.Frame:
    code = test_utils.parse(src)
    if name == '__main__':
      module_globals = (
          self.ctx.abstract_converter.get_module_globals(sys.version_info[:2]))
      initial_locals = initial_globals = {
          name: value.to_variable() for name, value in module_globals.items()}
    else:
      initial_locals = initial_globals = {}
    return frame_lib.Frame(self.ctx, name, code, initial_locals=initial_locals,
                           initial_globals=initial_globals)

  def _const_var(self, const, name=None):
    var = abstract.PythonConstant(self.ctx, const).to_variable()
    return var.with_name(name)


class ShadowedNonlocalsTest(unittest.TestCase):

  def test_enclosing(self):
    sn = frame_lib._ShadowedNonlocals()
    sn.add_enclosing('x')
    self.assertTrue(sn.has_scope('x', frame_lib._Scope.ENCLOSING))
    self.assertCountEqual(sn.get_names(frame_lib._Scope.ENCLOSING), {'x'})

  def test_global(self):
    sn = frame_lib._ShadowedNonlocals()
    sn.add_global('x')
    self.assertTrue(sn.has_scope('x', frame_lib._Scope.GLOBAL))
    self.assertCountEqual(sn.get_names(frame_lib._Scope.GLOBAL), {'x'})


class LoadStoreTest(FrameTestBase):

  def test_store_local_in_module_frame(self):
    frame = self._make_frame('', name='__main__')
    frame.step()
    var = abstract.PythonConstant(self.ctx, 5).to_variable()
    frame.store_local('x', var)
    stored = frame.load_local('x')
    self.assertEqual(stored, var.with_name('x'))
    self.assertEqual(stored, frame.load_global('x'))

  def test_store_local_in_nonmodule_frame(self):
    frame = self._make_frame('', name='f')
    frame.step()
    var = abstract.PythonConstant(self.ctx, 5).to_variable()
    frame.store_local('x', var)
    stored = frame.load_local('x')
    self.assertEqual(stored, var.with_name('x'))
    with self.assertRaises(KeyError):
      frame.load_global('x')

  def test_store_global_in_module_frame(self):
    frame = self._make_frame('', name='__main__')
    frame.step()
    var = abstract.PythonConstant(self.ctx, 5).to_variable()
    frame.store_global('x', var)
    stored = frame.load_global('x')
    self.assertEqual(stored, var.with_name('x'))
    self.assertEqual(stored, frame.load_local('x'))

  def test_store_global_in_nonmodule_frame(self):
    frame = self._make_frame('', name='f')
    frame.step()
    var = abstract.PythonConstant(self.ctx, 5).to_variable()
    frame.store_global('x', var)
    stored = frame.load_global('x')
    self.assertEqual(stored, var.with_name('x'))
    with self.assertRaises(KeyError):
      frame.load_local('x')

  def test_overwrite_global_in_module_frame(self):
    code = test_utils.parse('')
    var = abstract.PythonConstant(self.ctx, 5).to_variable()
    frame = frame_lib.Frame(
        self.ctx, '__main__', code, initial_locals={'x': var},
        initial_globals={'x': var})
    frame.step()

    self.assertEqual(frame.load_global('x'), var.with_name('x'))
    self.assertEqual(frame.load_local('x'), var.with_name('x'))

    var2 = abstract.PythonConstant(self.ctx, 10).to_variable()
    frame.store_global('x', var2)

    self.assertEqual(frame.load_global('x'), var2.with_name('x'))
    self.assertEqual(frame.load_local('x'), var2.with_name('x'))

  def test_overwrite_global_in_nonmodule_frame(self):
    code = test_utils.parse('')
    var = abstract.PythonConstant(self.ctx, 5).to_variable()
    frame = frame_lib.Frame(self.ctx, 'f', code, initial_globals={'x': var})
    frame.step()

    self.assertEqual(frame.load_global('x'), var.with_name('x'))
    with self.assertRaises(KeyError):
      frame.load_local('x')

    var2 = abstract.PythonConstant(self.ctx, 10).to_variable()
    frame.store_global('x', var2)

    self.assertEqual(frame.load_global('x'), var2.with_name('x'))
    with self.assertRaises(KeyError):
      frame.load_local('x')

  def test_enclosing(self):
    code = test_utils.parse('')
    frame = frame_lib.Frame(self.ctx, 'f', code)
    frame.step()
    x = abstract.PythonConstant(self.ctx, 5).to_variable()
    frame.store_enclosing('x', x)
    with self.assertRaises(KeyError):
      frame.load_local('x')
    with self.assertRaises(KeyError):
      frame.load_global('x')
    self.assertEqual(frame.load_enclosing('x'), x.with_name('x'))


class FrameTest(FrameTestBase):

  def test_run_no_crash(self):
    block = [opcodes.LOAD_CONST(0, 0, 0, None), opcodes.RETURN_VALUE(1, 0)]
    code = test_utils.FakeOrderedCode([block], [None])
    frame = frame_lib.Frame(self.ctx, 'test', code.Seal())
    frame.run()

  def test_typing(self):
    frame = self._make_frame('')
    assert_type(frame.final_locals, Mapping[str, abstract.BaseValue])

  def test_load_const(self):
    block = [opcodes.LOAD_CONST(0, 0, 0, 42), opcodes.RETURN_VALUE(1, 0)]
    code = test_utils.FakeOrderedCode([block], [42])
    frame = frame_lib.Frame(self.ctx, 'test', code.Seal())
    frame.step()
    self.assertEqual(len(frame._stack), 1)
    constant = frame._stack.top().get_atomic_value()
    self.assertEqual(constant, abstract.PythonConstant(self.ctx, 42))

  def test_store_local(self):
    frame = self._make_frame('x = 42')
    frame.run()
    self.assertIn('x', frame.final_locals)
    self.assertEqual(frame.final_locals['x'],
                     abstract.PythonConstant(self.ctx, 42))

  def test_store_global(self):
    frame = self._make_frame("""
      global x
      x = 42
    """)
    frame.run()
    self.assertIn('x', frame.final_locals)
    self.assertEqual(frame.final_locals['x'],
                     abstract.PythonConstant(self.ctx, 42))

  def test_function(self):
    frame = self._make_frame('def f(): pass')
    frame.run()
    self.assertIn('f', frame.final_locals)
    func = frame.final_locals['f']
    self.assertIsInstance(func, abstract.InterpreterFunction)
    self.assertEqual(func.name, 'f')
    self.assertCountEqual(frame.functions, [func])

  def test_copy_globals_from_module_frame(self):
    module_frame = self._make_frame("""
      x = 42
      def f():
        pass
    """, name='__main__')
    module_frame.run()
    f = _get(module_frame, 'f', _FrameFunction)
    f_frame = module_frame.make_child_frame(f, {})
    self.assertIn('x', f_frame._initial_globals)
    self.assertIn('f', f_frame._initial_globals)

  def test_copy_globals_from_nonmodule_frame(self):
    f_frame = self._make_frame("""
      global x
      x = 42
      def g():
        pass
    """, name='f')
    f_frame.run()
    g = _get(f_frame, 'g', _FrameFunction)
    g_frame = f_frame.make_child_frame(g, {})
    self.assertIn('x', g_frame._initial_globals)

  def test_copy_globals_from_inner_frame_to_module(self):
    module_frame = self._make_frame("""
      def f():
        global x
        x = 42
      f()
    """, name='__main__')
    module_frame.run()
    self.assertIn('f', module_frame.final_locals)
    self.assertIn('x', module_frame.final_locals)

  def test_copy_globals_from_inner_frame_to_outer(self):
    f_frame = self._make_frame("""
      def g():
        global x
        x = 42
      g()
    """, name='f')
    f_frame.run()
    self.assertIn('g', f_frame.final_locals)
    self.assertIn('x', f_frame.final_locals)
    self.assertCountEqual(
        f_frame._shadowed_nonlocals.get_names(frame_lib._Scope.GLOBAL), {'x'})

  def test_read_enclosing(self):
    module_frame = self._make_frame("""
      def f():
        x = None
        def g():
          y = x
    """)
    module_frame.run()
    f = _get(module_frame, 'f', _FrameFunction)
    f_frame = module_frame.make_child_frame(f, {})
    f_frame.run()
    g = _get(f_frame, 'g', _FrameFunction)
    g_frame = f_frame.make_child_frame(g, {})
    g_frame.run()
    self.assertIn('y', g_frame.final_locals)
    y = _get(g_frame, 'y', abstract.PythonConstant)
    self.assertIsNone(y.constant)
    self.assertIn('x', g_frame._initial_enclosing)

  def test_write_enclosing(self):
    module_frame = self._make_frame("""
      def f():
        x = None
        def g():
          nonlocal x
          x = 5
        g()
    """)
    module_frame.run()
    f = _get(module_frame, 'f', _FrameFunction)
    f_frame = module_frame.make_child_frame(f, {})
    f_frame.run()
    self.assertIn('x', f_frame.final_locals)
    self.assertIn('g', f_frame.final_locals)
    x = _get(f_frame, 'x', abstract.PythonConstant)
    self.assertEqual(x.constant, 5)

  def test_class(self):
    module_frame = self._make_frame('class C: ...')
    module_frame.run()
    cls = _get(module_frame, 'C', abstract.InterpreterClass)
    self.assertEqual(cls.name, 'C')

  def test_class_body(self):
    module_frame = self._make_frame("""
      class C:
        def f(self): ...
    """)
    module_frame.run()
    cls = _get(module_frame, 'C', abstract.InterpreterClass)
    self.assertIn('f', cls.members)
    f = cls.members['f']
    self.assertIsInstance(f, abstract.InterpreterFunction)
    self.assertEqual(f.name, 'C.f')

  def test_instance_attribute(self):
    module_frame = self._make_frame("""
      class C:
        def __init__(self):
          self.x = 3
    """)
    module_frame.run()
    cls = _get(module_frame, 'C', abstract.InterpreterClass)
    instance = cls.instantiate()
    self.assertEqual(instance.get_attribute('x'),
                     abstract.PythonConstant(self.ctx, 3))

  def test_read_instance_attribute(self):
    module_frame = self._make_frame("""
      class C:
        def __init__(self):
          self.x = 3
        def read(self):
          x = self.x
    """)
    module_frame.run()
    cls = _get(module_frame, 'C', abstract.InterpreterClass)
    instance = cls.instantiate()
    read = cast(abstract.InterpreterFunction, cls.members['read'])
    frame, = read.bind_to(instance).analyze()
    self.assertIn('x', frame.final_locals)
    self.assertEqual(frame.final_locals['x'],
                     abstract.PythonConstant(self.ctx, 3))

  def test_write_and_read_instance_attribute(self):
    module_frame = self._make_frame("""
      class C:
        def write_and_read(self):
          self.x = 3
          x = self.x
    """)
    module_frame.run()
    cls = _get(module_frame, 'C', abstract.InterpreterClass)
    instance = cls.instantiate()
    write_and_read = cast(abstract.InterpreterFunction,
                          cls.members['write_and_read'])
    frame, = write_and_read.bind_to(instance).analyze()
    self.assertIn('x', frame.final_locals)
    self.assertEqual(frame.final_locals['x'],
                     abstract.PythonConstant(self.ctx, 3))

  def test_modify_instance(self):
    module_frame = self._make_frame("""
      class C:
        def f(self):
          self.x = 3
      c = C()
      c.f()
    """)
    module_frame.run()
    c = _get(module_frame, 'c', abstract.MutableInstance)
    self.assertEqual(c.get_attribute('x'), abstract.PythonConstant(self.ctx, 3))

  def test_overwrite_instance_attribute(self):
    module_frame = self._make_frame("""
      class C:
        def f(self):
          self.x = 3
        def g(self):
          self.f()
          self.x = None
      c = C()
      c.g()
    """)
    module_frame.run()
    c = _get(module_frame, 'c', abstract.MutableInstance)
    self.assertEqual(c.get_attribute('x'),
                     abstract.PythonConstant(self.ctx, None))

  def test_instance_attribute_multiple_options(self):
    module_frame = self._make_frame("""
      class C:
        def __init__(self, rand):
          if rand:
            self.x = 3
          else:
            self.x = None
    """)
    module_frame.run()
    instance = _get(module_frame, 'C', abstract.InterpreterClass).instantiate()
    self.assertEqual(
        instance.get_attribute('x'),
        abstract.Union(self.ctx, (abstract.PythonConstant(self.ctx, 3),
                                  abstract.PythonConstant(self.ctx, None))))

  def test_multiple_initializers(self):
    module_frame = self._make_frame("""
      class C:
        def __init__(self, rand):
          if rand:
            self.x = 3
        def custom_init(self, rand):
          if rand:
            self.x = None
    """)
    module_frame.run()
    cls = _get(module_frame, 'C', abstract.InterpreterClass)
    cls.initializers.append('custom_init')
    instance = cls.instantiate()
    self.assertEqual(
        instance.get_attribute('x'),
        abstract.Union(self.ctx, (abstract.PythonConstant(self.ctx, 3),
                                  abstract.PythonConstant(self.ctx, None))))

  def test_return(self):
    module_frame = self._make_frame("""
      def f(rand):
        if rand:
          return 3
        else:
          return None
    """)
    module_frame.run()
    f = _get(module_frame, 'f', _FrameFunction)
    f_frame, = f.analyze()
    self.assertEqual(
        f_frame.get_return_value(),
        abstract.Union(self.ctx, (abstract.PythonConstant(self.ctx, 3),
                                  abstract.PythonConstant(self.ctx, None))))

  def test_stack(self):
    module_frame = self._make_frame('def f(): pass')
    self.assertEqual(module_frame.stack, [module_frame])

    module_frame.run()
    f = _get(module_frame, 'f', _FrameFunction)
    f_frame = module_frame.make_child_frame(f, {})
    self.assertEqual(f_frame.stack, [module_frame, f_frame])

  def test_stack_ops(self):
    """Basic smoke test for the stack manipulation ops."""
    # These just pass through to the underlying DataStack, which is well tested,
    # so we don't bother checking the stack contents here.
    block = [
        opcodes.LOAD_CONST(1, 0, 0, 1),  # 1
        opcodes.LOAD_CONST(2, 0, 1, 2),  # 2
        opcodes.LOAD_CONST(3, 0, 2, 3),  # 3
        opcodes.DUP_TOP(4, 0),           # 4
        opcodes.DUP_TOP_TWO(5, 0),       # 6
        opcodes.ROT_TWO(6, 0),           # 6
        opcodes.ROT_THREE(7, 0),         # 6
        opcodes.ROT_FOUR(8, 0),          # 6
        opcodes.ROT_N(9, 0, 2, 2),       # 6
        opcodes.POP_TOP(10, 0),          # 5
        opcodes.POP_TOP(11, 0),          # 4
        opcodes.POP_TOP(12, 0),          # 3
        opcodes.POP_TOP(13, 0),          # 2
        opcodes.POP_TOP(14, 0),          # 1
        opcodes.RETURN_VALUE(15, 0),     # 0
    ]
    code = test_utils.FakeOrderedCode([block], [1, 2, 3])
    frame = frame_lib.Frame(self.ctx, 'test', code.Seal())
    frame.run()  # Should not crash


class BuildConstantsTest(FrameTestBase):

  def _build_constant(self, code, typ=abstract.PythonConstant):
    module_frame = self._make_frame(code)
    module_frame.run()
    return _get(module_frame, 'constant', typ)

  def test_tuple(self):
    constant = self._build_constant("""
      a = 1
      b = 2
      c = 3
      constant = (a, b, c)
    """)
    self.assertEqual(constant.constant, (
        self._const_var(1, 'a'),
        self._const_var(2, 'b'),
        self._const_var(3, 'c'),
    ))

  def test_list(self):
    constant = self._build_constant("""
      a = 1
      b = 2
      c = 3
      constant = [a, b, c]
    """)
    self.assertEqual(constant.constant, [
        self._const_var(1, 'a'),
        self._const_var(2, 'b'),
        self._const_var(3, 'c'),
    ])

  def test_set(self):
    constant = self._build_constant("""
      a = 1
      b = 2
      c = 3
      constant = {a, b, c}
    """)
    self.assertEqual(constant.constant, {
        self._const_var(1, 'a'),
        self._const_var(2, 'b'),
        self._const_var(3, 'c'),
    })

  def test_map(self):
    constant = self._build_constant("""
      a = 1
      b = 2
      c = 3
      constant = {a: 1, b: 2, c: 3}
    """)
    self.assertEqual(constant.constant, {
        self._const_var(1, 'a'): self._const_var(1),
        self._const_var(2, 'b'): self._const_var(2),
        self._const_var(3, 'c'): self._const_var(3),
    })

  def test_const_key_map(self):
    constant = self._build_constant("""
      a = 1
      b = 2
      c = 3
      constant = {'a': a, 'b': b, 'c': c}
    """, typ=abstract.ConstKeyDict)
    self.assertEqual(constant.constant, {
        'a': self._const_var(1, 'a'),
        'b': self._const_var(2, 'b'),
        'c': self._const_var(3, 'c'),
    })


class ComprehensionAccumulatorTest(FrameTestBase):
  """Test accumulating results in a comprehension."""

  def test_list_append(self):
    block = [
        opcodes.BUILD_LIST(0, 0, 0, None),
        opcodes.LOAD_CONST(1, 0, 0, 1),
        opcodes.LOAD_CONST(2, 0, 1, 2),
        opcodes.LIST_APPEND(3, 0, 2, None),
        opcodes.NOP(4, 0)
    ]
    code = test_utils.FakeOrderedCode([block], [1, 2])
    frame = frame_lib.Frame(self.ctx, 'test', code.Seal())
    frame.stepn(4)
    target_var = frame._stack.peek(2)
    target = abstract.get_atomic_constant(target_var)
    self.assertEqual(target, [self._const_var(2)])

  def test_set_add(self):
    block = [
        opcodes.BUILD_SET(0, 0, 0, None),
        opcodes.LOAD_CONST(1, 0, 0, 1),
        opcodes.LOAD_CONST(2, 0, 1, 2),
        opcodes.SET_ADD(3, 0, 2, None),
        opcodes.NOP(4, 0)
    ]
    code = test_utils.FakeOrderedCode([block], [1, 2])
    frame = frame_lib.Frame(self.ctx, 'test', code.Seal())
    frame.stepn(4)
    target_var = frame._stack.peek(2)
    target = abstract.get_atomic_constant(target_var)
    self.assertEqual(target, {self._const_var(2)})

  def test_map_add(self):
    block = [
        opcodes.BUILD_MAP(0, 0, 0, None),
        opcodes.LOAD_CONST(1, 0, 0, 1),
        opcodes.LOAD_CONST(2, 0, 1, 2),
        opcodes.LOAD_CONST(3, 0, 2, 3),
        opcodes.MAP_ADD(4, 0, 2, None),
        opcodes.NOP(5, 0)
    ]
    code = test_utils.FakeOrderedCode([block], [1, 2, 3])
    frame = frame_lib.Frame(self.ctx, 'test', code.Seal())
    frame.stepn(5)
    target_var = frame._stack.peek(2)
    target = abstract.get_atomic_constant(target_var)
    self.assertEqual(target, {self._const_var(2): self._const_var(3)})


if __name__ == '__main__':
  unittest.main()
