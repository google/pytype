"""Test instance and class attributes."""

from pytype.tests import test_base


class TestStrictNone(test_base.TargetPython3BasicTest):
  """Tests for strict attribute checking on None."""

  def testExplicitNone(self):
    errors = self.CheckWithErrors("""\
            from typing import Optional
      def f(x: Optional[str]):
        return x.upper()
    """)
    self.assertErrorLogIs(errors, [(4, "attribute-error", r"upper.*None")])

  def testClosure(self):
    self.Check("""
            from typing import Optional
      d = ...  # type: Optional[dict]
      if d:
        formatter = lambda x: d.get(x, '')
      else:
        formatter = lambda x: ''
      formatter('key')
    """)

  def testOverwriteGlobal(self):
    errors = self.CheckWithErrors("""\
            from typing import Optional
      d = ...  # type: Optional[dict]
      if d:
        formatter = lambda x: d.get(x, '')  # line 5
      else:
        formatter = lambda x: ''
      d = None
      formatter('key')  # line 9
    """)
    self.assertErrorLogIs(
        errors, [(5, "attribute-error", "get.*None.*Traceback.*line 9")])


class TestAttributes(test_base.TargetPython3BasicTest):
  """Tests for attributes."""

  def testAttrOnOptional(self):
    errors = self.CheckWithErrors("""\
            from typing import Optional
      def f(x: Optional[str]):
        return x.upper()
    """)
    self.assertErrorLogIs(errors, [(4, "attribute-error", r"upper.*None")])

  def testErrorInAny(self):
    errors = self.CheckWithErrors("""\
            from typing import Any
      def f(x: Any):
        if __random__:
          x = 42
        x.upper()  # line 6
    """)
    self.assertErrorLogIs(
        errors, [(6, "attribute-error", r"upper.*int.*Union\[Any, int\]")])


class TestAttributesPython3FeatureTest(test_base.TargetPython3FeatureTest):
  """Tests for attributes over target code using Python 3 features."""

  def testEmptyTypeParameterInstance(self):
    self.Check("""
      args = {}
      for x, y in sorted(args.items()):
        x.values
    """)

  def testTypeParameterInstanceMultipleBindings(self):
    _, errors = self.InferWithErrors("""\
      class A(object):
        values = 42
      args = {A() if __random__ else True: ""}
      for x, y in sorted(args.items()):
        x.values  # line 5
    """)
    self.assertErrorLogIs(errors, [(5, "attribute-error", r"'values' on bool")])

  def testTypeParameterInstanceSetAttr(self):
    ty = self.Infer("""
      class Foo(object):
        pass
      class Bar(object):
        def bar(self):
          d = {42: Foo()}
          for _, foo in sorted(d.items()):
            foo.x = 42
    """)
    self.assertTypesMatchPytd(ty, """
      class Foo(object):
        x = ...  # type: int
      class Bar(object):
        def bar(self) -> None: ...
    """)

  def testTypeParameterInstance(self):
    ty = self.Infer("""
      class A(object):
        values = 42
      args = {A(): ""}
      for x, y in sorted(args.items()):
        z = x.values
    """, deep=False)
    self.assertTypesMatchPytd(ty, """
      from typing import Dict
      class A(object):
        values = ...  # type: int
      args = ...  # type: Dict[A, str]
      x = ...  # type: A
      y = ...  # type: str
      z = ...  # type: int
    """)


if __name__ == "__main__":
  test_base.main()
