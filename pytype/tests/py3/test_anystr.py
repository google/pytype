"""Tests for typing.AnyStr."""

from pytype import file_utils
from pytype.tests import test_base


class AnyStrTest(test_base.TargetPython3BasicTest):
  """Tests for issues related to AnyStr."""

  def testCallable(self):
    """Tests Callable + AnyStr."""
    self.Check("""
      from typing import AnyStr, Callable

      def f1(f: Callable[[AnyStr], AnyStr]):
        f2(f)
      def f2(f: Callable[[AnyStr], AnyStr]):
        pass
      """)

  def testUnknownAgainstMultipleAnyStr(self):
    self.Check("""
      from typing import Any, Dict, Tuple, AnyStr

      def foo(x: Dict[Tuple[AnyStr], AnyStr]): ...
      foo(__any_object__)
    """)

  def testMultipleUnknownAgainstMultipleAnyStr(self):
    self.Check("""
      from typing import AnyStr, List
      def foo(x: List[AnyStr], y: List[AnyStr]): ...
      foo(__any_object__, [__any_object__])
    """)

  def testAnyStrInClosure(self):
    self.assertNoCrash(self.Check, """
      from typing import AnyStr, Dict, Optional
      def foo(d: Dict[unicode, Optional[AnyStr]] = None):
        def bar() -> Optional[AnyStr]:
          return __any_object__
        d[__any_object__] = bar()
    """)


class AnyStrTestPy3(test_base.TargetPython3FeatureTest):
  """Tests for issues related to AnyStr in Python 3."""

  def testAnyStr(self):
    ty = self.Infer("""
      from typing import AnyStr
      def f(x: AnyStr) -> AnyStr:
        return __any_object__
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import TypeVar
      AnyStr = TypeVar("AnyStr", str, bytes)
      def f(x: AnyStr) -> AnyStr: ...
    """)
    self.assertTrue(ty.Lookup("f").signatures[0].template)

  def testAnyStrFunctionImport(self):
    with file_utils.Tempdir() as d:
      d.create_file("a.pyi", """
        from typing import AnyStr
        def f(x: AnyStr) -> AnyStr
      """)
      ty = self.Infer("""
        from a import f
      """, pythonpath=[d.path])
      self.assertTypesMatchPytd(ty, """
        from typing import TypesVar
        AnyStr = TypeVar("AnyStr", str, bytes)
        def f(x: AnyStr) -> AnyStr
      """)

  def testUseAnyStrConstraints(self):
    ty, errors = self.InferWithErrors("""\
      from typing import AnyStr, TypeVar
      def f(x: AnyStr, y: AnyStr) -> AnyStr:
        return __any_object__
      v1 = f(__any_object__, u"")  # ok
      v2 = f(__any_object__, 42)  # wrong-arg-types[e]
    """)
    self.assertTypesMatchPytd(ty, """
      from typing import Any, TypeVar
      AnyStr = TypeVar("AnyStr", str, bytes)
      def f(x: AnyStr, y: AnyStr) -> AnyStr: ...
      v1 = ...  # type: str
      v2 = ...  # type: Any
    """)
    self.assertErrorRegexes(errors, {"e": r"Union\[bytes, str\].*int"})

  def testConstraintMismatch(self):
    _, errors = self.InferWithErrors("""\
      from typing import AnyStr
      def f(x: AnyStr, y: AnyStr): ...
      f("", "")  # ok
      f("", b"")  # wrong-arg-types[e]
      f(b"", b"")  # ok
    """)
    self.assertErrorRegexes(
        errors, {"e": r"Expected.*y: str.*Actual.*y: bytes"})


test_base.main(globals(), __name__ == "__main__")
