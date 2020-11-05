"""Tests for control flow (with statements, loops, exceptions, etc.)."""

from pytype.tests import test_base


class FlowTest(test_base.TargetIndependentTest):
  """Tests for control flow.

  These tests primarily test instruction ordering and CFG traversal of the
  bytecode interpreter, i.e., their primary focus isn't the inferred types.
  Even though they check the validity of the latter, they're mostly smoke tests.
  """

  def test_if(self):
    ty = self.Infer("""
      if __random__:
        x = 3
      else:
        x = 3.1
    """, deep=False, show_library_calls=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Union
      x = ...  # type: Union[int, float]
    """)

  def test_exception(self):
    ty = self.Infer("""
      def f():
        try:
          x = UndefinedName()
        except Exception:
          return 3
      f()
    """, deep=False, show_library_calls=True,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_two_except_handlers(self):
    ty = self.Infer("""
      def f():
        try:
          x = UndefinedName()
        except Exception:
          return 3
        except:
          return 3.5
      f()
    """, deep=False, show_library_calls=True,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.intorfloat)

  def test_nested_exceptions(self):
    ty = self.Infer("""
      def f():
        try:
          try:
            UndefinedName()
          except:
            return 3
        except:
          return 3.5
      f()
    """, deep=False, show_library_calls=True,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_raise(self):
    ty = self.Infer("""
      def f():
        try:
          try:
            raise  # raises TypeError (exception not derived from BaseException)
          except:
            return 3
        except:
          return 3.5
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_finally(self):
    ty = self.Infer("""
      def f():
        try:
          x = RaiseANameError()
        finally:
          return 3
      f()
    """, deep=False, show_library_calls=True,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_finally_suffix(self):
    ty = self.Infer("""
      def f():
        try:
          x = RaiseANameError()
        finally:
          x = 3
        return x
      f()
    """, deep=False, show_library_calls=True,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_try_and_loop(self):
    ty = self.Infer("""
      def f():
        for s in (1, 2):
          try:
            try:
              pass
            except:
              continue
          finally:
            return 3
      f()
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def test_simple_with(self):
    ty = self.Infer("""
      def f(x):
        y = 1
        with __any_object__:
          y = 2
        return x
      f(1)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_nested_with(self):
    ty = self.Infer("""
      def f(x):
        y = 1
        with __any_object__:
          y = 2
          with __any_object__:
            pass
        return x
      f(1)
    """, deep=False, show_library_calls=True)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def test_null_flow(self):
    ty = self.Infer("""
      def f(x):
        if x is None:
          return 0
        return len(x)
      f(__any_object__)
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int: ...
    """)

  def test_continue_in_with(self):
    ty = self.Infer("""
      def f():
        l = []
        for i in range(3):
          with __any_object__:
            l.append(i)
            if i % 2:
               continue
            l.append(i)
          l.append(i)
        return l
      f()
    """, deep=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int_list)

  def test_break_in_with(self):
    ty = self.Infer("""
      def f():
        l = []
        for i in range(3):
          with __any_object__:
            l.append('w')
            if i % 2:
               break
            l.append('z')
          l.append('e')
        l.append('r')
        s = ''.join(l)
        return s
      f()
    """, deep=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.str)

  def test_raise_in_with(self):
    ty = self.Infer("""
      def f():
        l = []
        try:
          with __any_object__:
            l.append('w')
            raise ValueError("oops")
            l.append('z')
          l.append('e')
        except ValueError as e:
          assert str(e) == "oops"
          l.append('x')
        l.append('r')
        s = ''.join(l)
        return s
      f()
    """, deep=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.str)

  def test_return_in_with(self):
    ty = self.Infer("""
      def f():
        with __any_object__:
          return "foo"
      f()
    """, deep=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.str)

  def test_dead_if(self):
    self.Check("""
      x = None
      if x is not None:
        x.foo()
    """)
    self.Check("""
      x = 1
      if x is not 1:
        x.foo()
    """)

  def test_return_after_loop(self):
    ty = self.Infer("""
      def f():
        x = g()
        return x

      def g():
        while True:
          pass
        return 42
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f() -> Any: ...
      def g() -> Any: ...
    """)

  def test_change_boolean(self):
    ty = self.Infer("""
      def f():
        b = True
        while b:
          b = False
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      def f() -> Any: ...
    """)

  def test_independent_calls(self):
    ty = self.Infer("""
      class _Item(object):
        def __init__(self, stack):
          self.name = "foo"
          self.name_list = [s.name for s in stack]
      def foo():
        stack = []
        if __random__:
          stack.append(_Item(stack))
        else:
          stack.append(_Item(stack))
    """)
    self.assertTypesMatchPytd(ty, """
      class _Item(object):
        name = ...  # type: str
        name_list = ...  # type: list
        def __init__(self, stack) -> None: ...
      def foo() -> None: ...
    """)

  def test_duplicate_getproperty(self):
    ty = self.Infer("""
      class Foo(object):
        def __init__(self):
          self._node = __any_object__
        def bar(self):
          if __random__:
            raise Exception(
            'No node with type %s could be extracted.' % self._node)
      Foo().bar()
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        _node = ...  # type: Any
        def __init__(self) -> None: ...
        def bar(self) -> NoneType: ...
    """)

  def test_break(self):
    ty = self.Infer("""
      def _foo():
        while True:
          if __random__:
            break
        return 3j
    """)
    self.assertTypesMatchPytd(ty, """
      def _foo() -> complex: ...
    """)

  def test_continue(self):
    ty = self.Infer("""
      def bar():
        while True:
          if __random__:
            return 3j
          continue
          return 3  # dead code
    """)
    self.assertTypesMatchPytd(ty, """
      def bar() -> complex: ...
    """)

  def test_loop_over_list_of_lists(self):
    ty = self.Infer("""
      import os
      for seq in [os.getgroups()]:  # os.getgroups() returns a List[int]
        seq.append("foo")
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import List, Union
      os = ...  # type: module
      seq = ...  # type: List[Union[int, str]]
    """)

  def test_call_undefined(self):
    _, errors = self.InferWithErrors("""
      def f():
        try:
          func = None
        except:
          func()  # name-error[e]
    """, deep=True)
    self.assertErrorRegexes(errors, {"e": r"func"})

  def test_nested_break(self):
    self.assertNoCrash(self.Infer, """
      while True:
        try:
          pass
        except:
          break
        while True:
          try:
            pass
          except:
            break
    """)

  def test_nested_break2(self):
    self.assertNoCrash(self.Infer, """
      while True:
        for x in []:
          pass
        break
    """)

  def test_loop_after_break(self):
    self.assertNoCrash(self.Infer, """
      for _ in ():
        break
      else:
        raise
      for _ in ():
        break
      else:
        raise
    """)

  def test_recursion(self):
    ty = self.Infer("""
      b = True
      def f():
        if b:
          g()
      def g():
        global b
        b = False
        f()
    """)
    self.assertTypesMatchPytd(ty, """
      b = ...  # type: bool
      def f() -> None: ...
      def g() -> None: ...
    """)


test_base.main(globals(), __name__ == "__main__")
