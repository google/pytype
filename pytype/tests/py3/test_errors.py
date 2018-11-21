"""Tests for displaying errors."""

from pytype import file_utils
from pytype.tests import test_base


class ErrorTest(test_base.TargetPython3BasicTest):
  """Tests for errors."""

  def testUnion(self):
    _, errors = self.InferWithErrors("""\
      def f(x: int):
        pass
      if __random__:
        i = 0
      else:
        i = 1
      x = (3.14, "")
      f(x[i])
    """)
    self.assertErrorLogIs(errors, [(8, "wrong-arg-types",
                                    r"Actually passed:.*Union\[float, str\]")])

  def testInvalidAnnotations(self):
    _, errors = self.InferWithErrors("""\
      from typing import Dict, List, Union
      def f1(x: Dict):  # okay
        pass
      def f2(x: Dict[str]):
        pass
      def f3(x: List[int, str]):
        pass
      def f4(x: Union):
        pass
    """)
    self.assertErrorLogIs(errors, [
        (4, "invalid-annotation", r"typing.Dict\[_K, _V].*2.*1"),
        (6, "invalid-annotation", r"typing.List\[_T].*1.*2"),
        (8, "invalid-annotation", r"Union.*x")])

  def testPrintUnsolvable(self):
    _, errors = self.InferWithErrors("""\
      from typing import List
      def f(x: List[nonsense], y: str, z: float):
        pass
      f({nonsense}, "", "")
    """)
    self.assertErrorLogIs(errors, [
        (2, "name-error", r"nonsense"),
        (4, "name-error", r"nonsense"),
        (4, "wrong-arg-types", r"Expected:.*x: list.*Actual.*x: set")])

  def testPrintUnionOfContainers(self):
    _, errors = self.InferWithErrors("""\
      def f(x: str):
        pass
      if __random__:
        x = dict
      else:
        x = [float]
      f(x)
    """)
    error = r"Actual.*Union\[List\[Type\[float\]\], Type\[dict\]\]"
    self.assertErrorLogIs(errors, [(7, "wrong-arg-types", error)])

  def testWrongBrackets(self):
    _, errors = self.InferWithErrors("""\
      from typing import List
      def f(x: List(str)):
        pass
    """)
    self.assertErrorLogIs(errors, [(2, "not-callable", r"List")])

  def testInterpreterClassPrinting(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object): pass
      def f(x: str): pass
      f(Foo())
    """)
    self.assertErrorLogIs(errors, [(3, "wrong-arg-types", r"str.*Foo")])

  def testPrintDictAndTuple(self):
    _, errors = self.InferWithErrors("""\
      from typing import Tuple
      tup = None  # type: Tuple[int, ...]
      dct = None  # type: dict[str, int]
      def f1(x: (int, str)):  # line 4
        pass
      def f2(x: tup):  # line 6
        pass
      def g1(x: {"a": 1}):  # line 8
        pass
      def g2(x: dct):  # line 10
        pass
    """)
    self.assertErrorLogIs(errors, [
        (4, "invalid-annotation", r"(int, str).*Not a type"),
        (6, "invalid-annotation",
         r"instance of Tuple\[int, \.\.\.\].*Not a type"),
        (8, "invalid-annotation", r"{'a': '1'}.*Not a type"),
        (10, "invalid-annotation", r"instance of Dict\[str, int\].*Not a type")
    ])

  def testMoveUnionInward(self):
    _, errors = self.InferWithErrors("""\
      def f() -> str:
        y = "hello" if __random__ else 42
        yield y
    """)
    self.assertErrorLogIs(errors, [(
        1, "invalid-annotation", r"Generator, Iterable or Iterator")])

  def testInnerClassError(self):
    _, errors = self.InferWithErrors("""\
      def f(x: str): pass
      def g():
        class Foo(object): pass
        f(Foo())
    """)
    self.assertErrorLogIs(errors, [(4, "wrong-arg-types", r"x: str.*x: Foo")])

  def testInnerClassError2(self):
    _, errors = self.InferWithErrors("""\
      def f():
        class Foo(object): pass
        def g(x: Foo): pass
        g("")
    """)
    self.assertErrorLogIs(errors, [(4, "wrong-arg-types", r"x: Foo.*x: str")])

  def testCleanNamedtupleNames(self):
    # Make sure the namedtuple renaming in _pytd_print correctly extracts type
    # names and doesn't erase other types accidentally.
    _, errors = self.InferWithErrors("""\
      import collections
      X = collections.namedtuple("X", "a b c d")
      Y = collections.namedtuple("Z", "")
      W = collections.namedtuple("W", "abc def ghi abc", rename=True)
      def bar(x: str):
        return x
      bar(X(1,2,3,4))  # 7
      bar(Y())         # 8
      bar(W(1,2,3,4))  # 9
      bar({1: 2}.__iter__())  # 10
      if __random__:
        a = X(1,2,3,4)
      else:
        a = 1
      bar(a)  # 15
      """)
    self.assertErrorLogIs(errors,
                          [(7, "wrong-arg-types", r"`X`"),
                           (8, "wrong-arg-types", r"`Z`"),
                           (9, "wrong-arg-types", r"`W`"),
                           (10, "wrong-arg-types", r"`dictionary-keyiterator`"),
                           (15, "wrong-arg-types", r"Union\[int, `X`\]")
                          ])

  def testArgumentOrder(self):
    _, errors = self.InferWithErrors("""\
      def g(f: str, a, b, c, d, e,):
        pass
      g(a=1, b=2, c=3, d=4, e=5, f=6)
      """)
    self.assertErrorLogIs(
        errors,
        [(3, "wrong-arg-types",
          r"Expected.*f: str, \.\.\..*Actual.*f: int, \.\.\.")]
    )

  def testConversionOfGeneric(self):
    _, errors = self.InferWithErrors("""
      import os
      def f() -> None:
        return os.walk("/tmp")
    """)
    self.assertErrorLogIs(errors, [
        (4, "bad-return-type")
    ])

  def testInnerClass(self):
    _, errors = self.InferWithErrors("""\
      def f() -> int:
        class Foo(object):
          pass
        return Foo()  # line 4
    """)
    self.assertErrorLogIs(errors, [(4, "bad-return-type", r"int.*Foo")])

  def testNestedProtoClass(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo_bar.pyi", """
        from typing import Type
        class _Foo_DOT_Bar: ...
        class Foo:
          Bar = ...  # type: Type[_Foo_DOT_Bar]
      """)
      errors = self.CheckWithErrors("""\
        import foo_bar
        def f(x: foo_bar.Foo.Bar): ...
        f(42)
      """, pythonpath=[d.path])
      self.assertErrorLogIs(
          errors, [(3, "wrong-arg-types", r"foo_bar\.Foo\.Bar")])

  def testStaticmethodInError(self):
    with file_utils.Tempdir() as d:
      d.create_file("foo.pyi", """\
        class A(object):
          @staticmethod
          def t(a: str) -> None: ...
        """)
      errors = self.CheckWithErrors("""\
        from typing import Callable
        import foo
        def f(x: Callable[[int], None], y: int) -> None:
          return x(y)
        f(foo.A.t, 1)
        """, pythonpath=[d.path])
      self.assertErrorLogIs(
          errors,
          [(5, "wrong-arg-types",
            r"Actually passed: \(x: Callable\[\[str\], None\]")])

  def testGeneratorSend(self):
    errors = self.CheckWithErrors("""\
      from typing import Generator, Any
      def f(x) -> Generator[Any, int, Any]:
        if x == 1:
          yield 1
        else:
          yield "1"

      x = f(2)
      x.send("123")
    """)
    self.assertErrorLogIs(errors, [(9, "wrong-arg-types",
                                    r"\(self, value: int\)")])

  def testGeneratorIteratorRetType(self):
    errors = self.CheckWithErrors("""\
      from typing import Iterator
      def f() -> Iterator[str]:
        yield 1
    """)
    self.assertErrorLogIs(errors, [(3, "bad-return-type", r"str.*int")])

  def testGeneratorIterableRetType(self):
    errors = self.CheckWithErrors("""\
      from typing import Iterable
      def f() -> Iterable[str]:
        yield 1
    """)
    self.assertErrorLogIs(errors, [(3, "bad-return-type", r"str.*int")])


class ErrorTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for errors."""

  def testProtocolMismatch(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object): pass
      next(Foo())
    """)
    self.assertErrorLogIs(errors, [
        (2, "wrong-arg-types", "__iter__, __next__")
    ])

  def testProtocolMismatchPartial(self):
    _, errors = self.InferWithErrors("""\
      class Foo(object):
        def __iter__(self):
          return self
      next(Foo())
    """)
    self.assertErrorLogIs(errors, [(
        4, "wrong-arg-types", r"\n\s*__next__\s*$")])  # `next` on its own line

  def testGeneratorSendRetType(self):
    _, errors = self.InferWithErrors("""\
      from typing import Generator
      def f() -> Generator[int, str, int]:
        x = yield 1
        return x
    """)
    self.assertErrorLogIs(errors, [(4, "bad-return-type", r"int.*str")])


test_base.main(globals(), __name__ == "__main__")
