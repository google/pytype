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
        X(42)  # wrong-arg-types[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"X.*int"})

  def testBadReturnTypeInline(self):
    errorlog = self.CheckWithErrors("""\
      from typing import List
      def f() -> List[int]:
        return [object()]  # bad-return-type[e]
      f()[0] += 1
    """)
    self.assertErrorRegexes(errorlog, {"e": r"List\[int\].*List\[object\]"})

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
        return {"x": 42.0}  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"int.*float"})

  def testInstanceAsAnnotation(self):
    errorlog = self.CheckWithErrors("""\
      def f():
        pass
      def g(x: f):  # invalid-annotation[e1]
        pass
      def h(x: 3):  # invalid-annotation[e2]
        pass
    """)
    self.assertErrorRegexes(
        errorlog, {"e1": r"instance of Callable.*x", "e2": r"3.*x"})

  def testBadGenerator(self):
    errorlog = self.CheckWithErrors("""\
      from typing import Generator
      def f() -> Generator[str, None, None]:
        for i in range(3):
          yield i  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"str.*int"})

  def testMultipleParameterBindings(self):
    errorlog = self.CheckWithErrors("""\
      from typing import List
      def f(x) -> List[int]:
        return ["", x]  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"List\[int\].*List\[str\]"})

  def testNoParamBinding(self):
    errorlog = self.CheckWithErrors("""\
      def f() -> None:
        x = []
        return x  # bad-return-type[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"None.*List\[nothing\]"})

  def testAttributeInIncompleteInstance(self):
    errorlog = self.CheckWithErrors("""\
      from typing import List
      class Foo(object):
        def __init__(self, other: "List[Foo]"):
          self.x = other[0].x  # okay
          # No "y" on List[Foo]
          self.y = other.y  # attribute-error[e1]
          # No "z" on Type[Foo]
          self.z = Foo.z  # attribute-error[e2]
    """)
    self.assertErrorRegexes(errorlog, {"e1": r"y.*List\[Foo\]",
                                       "e2": r"z.*Type\[Foo\]"})

  def testBadGetItem(self):
    errorlog = self.CheckWithErrors("""\
      def f(x: int):
        return x[0]  # unsupported-operands[e]
    """)
    self.assertErrorRegexes(errorlog, {"e": r"int.*int"})

  def testBadAnnotationContainer(self):
    errorlog = self.CheckWithErrors("""\
      class A(object):
        pass
      def f(x: int[str]):  # not-indexable[e1]
        pass
      def g(x: A[str]):  # not-indexable[e2]
        pass
    """)
    self.assertErrorRegexes(errorlog, {"e1": r"Generic", "e2": r"Generic"})


test_base.main(globals(), __name__ == "__main__")
