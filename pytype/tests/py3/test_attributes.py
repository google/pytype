"""Test instance and class attributes."""

from pytype.tests import test_base


class TestStrictNone(test_base.TargetPython3BasicTest):
  """Tests for strict attribute checking on None."""

  def testExplicitNone(self):
    errors = self.CheckWithErrors("""\
      from typing import Optional
      def f(x: Optional[str]):
        return x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

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
        formatter = lambda x: d.get(x, '')  # attribute-error[e]
      else:
        formatter = lambda x: ''
      d = None
      formatter('key')  # line 8
    """)
    self.assertErrorRegexes(errors, {"e": r"get.*None.*traceback.*line 8"})


class TestAttributes(test_base.TargetPython3BasicTest):
  """Tests for attributes."""

  def testAttrOnOptional(self):
    errors = self.CheckWithErrors("""\
      from typing import Optional
      def f(x: Optional[str]):
        return x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*None"})

  def testErrorInAny(self):
    errors = self.CheckWithErrors("""\
      from typing import Any
      def f(x: Any):
        if __random__:
          x = 42
        x.upper()  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"upper.*int.*Union\[Any, int\]"})


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
        x.values  # attribute-error[e]
    """)
    self.assertErrorRegexes(errors, {"e": r"'values' on bool"})

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

  def testFilterSubclassAttribute(self):
    self.Check("""
      from typing import List

      class NamedObject(object):
        name = ...  # type: str
      class UnnamedObject(object):
        pass
      class ObjectHolder(object):
        named = ...  # type: NamedObject
        unnamed = ...  # type: UnnamedObject

      class Base(object):
        def __init__(self):
          self.objects = []  # type: List

      class Foo(Base):
        def __init__(self, holder: ObjectHolder):
          Base.__init__(self)
          self.objects.append(holder.named)
        def get_name(self):
          return self.objects[0].name

      class Bar(Base):
        def __init__(self, holder: ObjectHolder):
          Base.__init__(self)
          self.objects = []
          self.objects.append(holder.unnamed)
    """)

  @test_base.skip("Needs vm._get_iter() to iterate over individual bindings.")
  def testMetaclassIter(self):
    self.Check("""
      class Meta(type):
        def __iter__(cls):
          return iter([])
      class Foo(metaclass=Meta):
        def __iter__(self):
          return iter([])
      for _ in Foo:
        pass
    """)

  @test_base.skip("Needs better handling of __getitem__ in vm._get_iter().")
  def testMetaclassGetItem(self):
    self.Check("""
      class Meta(type):
        def __getitem__(cls, x):
          return 0
      class Foo(metaclass=Meta):
        def __getitem__(self, x):
          return 0
      for _ in Foo:
        pass
    """)


test_base.main(globals(), __name__ == "__main__")
