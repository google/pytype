"""Tests for --check."""

from pytype.tests import test_base


class CheckerTest(test_base.TargetPython3BasicTest):
  """Tests for --check."""

  def testSet(self):
    self.Check("""
            from typing import List, Set
      def f(data: List[str]):
        data = set(x for x in data)
        g(data)
      def g(data: Set[str]):
        pass
    """)

  def testRecursiveForwardReference(self):
    errorlog = self.CheckWithErrors("""\
            class X(object):
        def __init__(self, val: "X"):
          pass
      def f():
        X(42)
    """)
    self.assertErrorLogIs(errorlog, [(6, "wrong-arg-types", r"X.*int")])

  def testBadReturnTypeInline(self):
    errorlog = self.CheckWithErrors("""\
            from typing import List
      def f() -> List[int]:
        return [object()]
      f()[0] += 1
    """)
    self.assertErrorLogIs(errorlog, [(4, "bad-return-type",
                                      r"List\[int\].*List\[object\]")])

  def testUseVarargsAndKwargs(self):
    self.Check("""\
            class A(object):
        pass
      def f(*args: A, **kwargs: A):
        for arg in args:
          pass
        for kwarg in kwargs:
          pass
    """)

  def testNestedNoneType(self):
    self.Check("""\
            from typing import List, Union
      def f1() -> Union[None]:
        pass
      def f2() -> List[None]:
        return [None]
      def g1(x: Union[None]):
        pass
      def g2(x: List[None]):
        pass
    """)

  def testInnerClassInit(self):
    self.Check("""\
            from typing import List
      class A:
        def __init__(self):
          self.x = 42
      def f(v: List[A]):
        return v[0].x
      def g() -> List[A]:
        return [A()]
      def h():
        return g()[0].x
    """)

  def testRecursion(self):
    self.Check("""\
            class A:
        def __init__(self, x: "B"):
          pass
      class B:
        def __init__(self):
          self.x = 42
          self.y = A(self)
    """)

  def testBadDictValue(self):
    errorlog = self.CheckWithErrors("""\
            from typing import Dict
      def f() -> Dict[str, int]:
        return {"x": 42.0}
    """)
    self.assertErrorLogIs(errorlog, [(4, "bad-return-type", r"int.*float")])

  def testInstanceAsAnnotation(self):
    errorlog = self.CheckWithErrors("""\
            def f():
        pass
      def g(x: f):
        pass
      def h(x: 3):
        pass
    """)
    self.assertErrorLogIs(errorlog, [(4, "invalid-annotation",
                                      r"instance of Callable.*x"),
                                     (6, "invalid-annotation",
                                      r"3.*x")])

  def testBadGenerator(self):
    errorlog = self.CheckWithErrors("""\
            from typing import Generator
      def f() -> Generator[str]:
        for i in range(3):
          yield i
    """)
    self.assertErrorLogIs(errorlog, [(5, "bad-return-type",
                                      r"Generator\[str, Any, Any\].*"
                                      r"Generator\[int, None, None\]")])

  def testMultipleParameterBindings(self):
    errorlog = self.CheckWithErrors("""\
            from typing import List
      def f(x) -> List[int]:
        return ["", x]
    """)
    self.assertErrorLogIs(errorlog, [(4, "bad-return-type",
                                      r"List\[int\].*List\[str\]")])

  def testNoParamBinding(self):
    errorlog = self.CheckWithErrors("""\
            def f() -> None:
        x = []
        return x
    """)
    self.assertErrorLogIs(errorlog, [(4, "bad-return-type",
                                      r"None.*List\[nothing\]")])

  def testAttributeInIncompleteInstance(self):
    errorlog = self.CheckWithErrors("""\
            from typing import List
      class Foo(object):
        def __init__(self, other: "List[Foo]"):
          self.x = other[0].x  # okay
          self.y = other.y  # No "y" on List[Foo]
          self.z = Foo.z  # No "z" on Type[Foo]
    """)
    self.assertErrorLogIs(errorlog, [(6, "attribute-error", r"y.*List\[Foo\]"),
                                     (7, "attribute-error", r"z.*Type\[Foo\]")])

  def testBadGetItem(self):
    errorlog = self.CheckWithErrors("""\
            def f(x: int):
        return x[0]
    """)
    self.assertErrorLogIs(errorlog, [(3, "unsupported-operands", r"int.*int")])

  def testBadAnnotationContainer(self):
    errorlog = self.CheckWithErrors("""\
            class A(object):
        pass
      def f(x: int[str]):
        pass
      def g(x: A[str]):
        pass
    """)
    self.assertErrorLogIs(errorlog, [(4, "not-indexable", r"Generic"),
                                     (6, "not-indexable", r"Generic")])


if __name__ == "__main__":
  test_base.main()
