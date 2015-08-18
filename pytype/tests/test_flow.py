"""Tests for control flow (with statements, loops, exceptions, etc.)."""

from pytype.tests import test_inference


class FlowTest(test_inference.InferenceTest):
  """Tests for control flow.

  These tests primarily test instruction ordering and CFG traversal of the
  bytecode interpreter, i.e., their primary focus isn't the inferred types.
  Even though they check the validity of the latter, they're mostly smoke tests.
  """

  def test_if(self):
    with self.Infer("""
      if __random__:
        x = 3
      else:
        x = 3.1
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertTypesMatchPytd(ty, """
        x: int or float
      """)

  def testException(self):
    with self.Infer("""
      def f():
        try:
          x = UndefinedName()
        except Exception, error:
          return 3
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testTwoExceptHandlers(self):
    with self.Infer("""
      def f():
        try:
          x = UndefinedName()
        except Exception, error:
          return 3
        except:
          return 3.5
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.intorfloat)

  def testNestedExceptions(self):
    with self.Infer("""
      def f():
        try:
          try:
            UndefinedName()
          except:
            return 3
        except:
          return 3.5
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testRaise(self):
    with self.Infer("""
      def f():
        try:
          try:
            raise  # raises TypeError (exception not derived from BaseException)
          except:
            return 3
        except:
          return 3.5
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testFinally(self):
    with self.Infer("""
      def f():
        try:
          x = RaiseANameError()
        finally:
          return 3
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testFinallySuffix(self):
    with self.Infer("""
      def f():
        try:
          x = RaiseANameError()
        finally:
          x = 3
        return x
      f()
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testTryAndLoop(self):
    with self.Infer("""
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
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int)

  def testSimpleWith(self):
    with self.Infer("""
      def f(x):
        y = 1
        with __any_object__:
          y = 2
        return x
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
      self.assertHasSignature(ty.Lookup("f"), (self.int,), self.int)

  def testNestedWith(self):
    with self.Infer("""
      def f(x):
        y = 1
        with __any_object__:
          y = 2
          with __any_object__:
            pass
        return x
      f(1)
    """, deep=False, solve_unknowns=False, extract_locals=False) as ty:
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
    with self.Infer("""
      def f(x):
        if x is None:
          return 0
        # else
        # return x.__len__()  # TODO(pludemann): why doesn't this return int?
        return len(x)
      # f(None)  # TODO(pludemann): reinstate this
      f(__any_object__)
    """, deep=False, solve_unknowns=False, extract_locals=True) as ty:
      self.assertTypesMatchPytd(ty, """
        def f(x) -> int
      """)

  def testContinueInWith(self):
    with self.Infer("""
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
    """, deep=False, solve_unknowns=False, extract_locals=True) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.int_list)

  def testBreakInWith(self):
    with self.Infer("""
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
    """, deep=False, solve_unknowns=False, extract_locals=True) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.str)

  def testRaiseInWith(self):
    with self.Infer("""
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
    """, deep=False, solve_unknowns=False, extract_locals=True) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.str)

  def testReturnInWith(self):
    with self.Infer("""
      def f():
        with __any_object__:
          return "foo"
      f()
    """, deep=False, solve_unknowns=False, extract_locals=True) as ty:
      self.assertHasSignature(ty.Lookup("f"), (), self.str)


if __name__ == "__main__":
  test_inference.main()
