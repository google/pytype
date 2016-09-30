"""Tests for control flow (with statements, loops, exceptions, etc.)."""

from pytype.tests import test_inference


class FlowTest(test_inference.InferenceTest):
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
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertTypesMatchPytd(ty, """
      x = ...  # type: int or float
    """)

  def testException(self):
    ty = self.Infer("""
      def f():
        try:
          x = UndefinedName()
        except Exception, error:
          return 3
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testTwoExceptHandlers(self):
    ty = self.Infer("""
      def f():
        try:
          x = UndefinedName()
        except Exception, error:
          return 3
        except:
          return 3.5
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.intorfloat)

  def testNestedExceptions(self):
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
    """, deep=False, solve_unknowns=False, extract_locals=False,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testRaise(self):
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
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testFinally(self):
    ty = self.Infer("""
      def f():
        try:
          x = RaiseANameError()
        finally:
          return 3
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testFinallySuffix(self):
    ty = self.Infer("""
      def f():
        try:
          x = RaiseANameError()
        finally:
          x = 3
        return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False,
                    report_errors=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testTryAndLoop(self):
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
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testSimpleWith(self):
    ty = self.Infer("""
      def f(x):
        y = 1
        with __any_object__:
          y = 2
        return x
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testNestedWith(self):
    ty = self.Infer("""
      def f(x):
        y = 1
        with __any_object__:
          y = 2
          with __any_object__:
            pass
        return x
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False)
    self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testNullFLow(self):
    # This example comes from
    # https://code.prod.facebook.com/posts/1505962329687926/flow-a-new-static-type-checker-for-javascript/
    # although written a bit differently. We should try variants too. ;)
    # Also try a version without the test for "x is None", - should get error.
    # e.g.: return len(x) if x else 0
    # TODO(pludemann): add other examples from
    #                  http://flowtype.org/docs/five-simple-examples.html#_ and
    #                  also from Python mailing list discussion of typing, e.g.:
    #                  https://mail.python.org/pipermail/python-ideas/2014-December/thread.html#30430
    ty = self.Infer("""
      def f(x):
        if x is None:
          return 0
        # else
        # return x.__len__()  # TODO(pludemann): why doesn't this return int?
        return len(x)
      # f(None)  # TODO(pludemann): reinstate this
      f(__any_object__)
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertTypesMatchPytd(ty, """
      def f(x) -> int
    """)

  def testContinueInWith(self):
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
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.int_list)

  def testBreakInWith(self):
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
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.str)

  def testRaiseInWith(self):
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
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.str)

  def testReturnInWith(self):
    ty = self.Infer("""
      def f():
        with __any_object__:
          return "foo"
      f()
    """, deep=False, solve_unknowns=False, extract_locals=True)
    self.assertHasSignature(ty.Lookup("f"), (), self.str)

  def test_dead_if(self):
    self.assertNoErrors("""
      x = None
      if x is not None:
        x.foo()
    """)
    self.assertNoErrors("""
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
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      def f() -> Any
      def g() -> Any
    """)

  def test_independent_calls(self):
    ty = self.Infer("""
      class _Item(object):
        def __init__(self, stack):
          self.name = "foo"
          self.name_list = [s.name for s in stack]
      def foo():
        stack = []
        if __any_object__:
          stack.append(_Item(stack))
        else:
          stack.append(_Item(stack))
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
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
          if __any_object__:
            raise Exception(
            'No node with type %s could be extracted.' % self._node)
      Foo().bar()
    """, deep=True, solve_unknowns=True)
    self.assertTypesMatchPytd(ty, """
      from typing import Any
      class Foo(object):
        _node = ...  # type: Any
        def bar(self) -> NoneType: ...
    """)


if __name__ == "__main__":
  test_inference.main()
